# app/routes/upload.py
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from .. import utils, tasks, models
from ..db import get_db
from ..schemas import JobCreateResponse
from .dependencies import get_current_user
from ..s3_service import s3_service
from ..s3_config import s3_config
from ..dynamodb_service import dynamodb_service
from ..sqs_service import SQSService
import aiofiles
from typing import Optional

router = APIRouter()
sqs_service = SQSService()

# AWS TODO (S3 Presigned Upload):
# - Instead of uploading file bytes to the server, generate and return an S3 pre-signed PUT URL:
#   * server: boto3.client('s3').generate_presigned_url('put_object', Params={'Bucket': S3_BUCKET, 'Key': key}, ...)
#   * client: uploads directly to S3 using the URL
# - Persist Video/Job records after client confirms successful S3 upload (or use callback/verification)
# - Replace local save_path with an S3 key reference stored in DB

@router.post("/upload", response_model=JobCreateResponse)
async def upload_video(file: UploadFile = File(...),
                       db: Session = Depends(get_db),
                       user: dict = Depends(get_current_user)):
    """Upload video file to S3 and create processing job"""
    job_id = utils.make_job_id()
    
    # Generate S3 key for uploaded file
    s3_key = s3_config.get_upload_key(file.filename)
    
    try:
        # Upload file to S3
        upload_result = s3_service.upload_file(
            file.file,
            s3_key,
            content_type=file.content_type
        )
        
        # Persist Video & Job records
        video = models.Video(
            filename=file.filename, 
            owner=user["username"],
            s3_key=s3_key,  # Store S3 key instead of local path
            s3_url=upload_result['url']
        )
        db.add(video)
        db.commit()
        db.refresh(video)

        job = models.Job(
            job_id=job_id, 
            video_id=video.id, 
            status="queued",
            s3_input_key=s3_key  # Store S3 key for processing
        )
        db.add(job)
        db.commit()

        # Create job progress record in DynamoDB
        dynamodb_service.create_job_progress(
            job_id=job_id,
            video_filename=file.filename,
            owner=user["username"]
        )

        # Dispatch processing job via SQS
        sqs_service.send_job_message(job_id, s3_key, user["username"])

        return {"job_id": job_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/upload/presigned")
async def get_presigned_upload_url(
    filename: str = Form(...),
    content_type: str = Form(...),
    user: dict = Depends(get_current_user)
):
    """Get pre-signed URL for direct client upload to S3"""
    # Debug: Print received parameters
    print(f"🔍 Received filename: {filename} (type: {type(filename)})")
    print(f"🔍 Received content_type: {content_type} (type: {type(content_type)})")
    print(f"🔍 Received user: {user}")
    
    job_id = utils.make_job_id()
    s3_key = s3_config.get_upload_key(filename)
    
    try:
        # Generate pre-signed upload URL
        upload_url = s3_service.generate_presigned_upload_url(
            s3_key, 
            content_type
        )
        
        return {
            "job_id": job_id,
            "upload_url": upload_url,
            "s3_key": s3_key,
            "fields": {
                "key": s3_key,
                "Content-Type": content_type
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate upload URL: {str(e)}")

@router.post("/upload/test-form")
async def test_form_data(
    filename: str = Form(...),
    content_type: str = Form(...)
):
    """Test endpoint to verify form data parsing"""
    return {
        "message": "Form data received successfully",
        "filename": filename,
        "content_type": content_type,
        "filename_type": str(type(filename)),
        "content_type_type": str(type(content_type))
    }

@router.post("/upload/debug-presigned")
async def debug_presigned_url(
    filename: str = Form(...),
    content_type: str = Form(...),
    user: dict = Depends(get_current_user)
):
    """Debug endpoint to test presigned URL generation"""
    job_id = utils.make_job_id()
    s3_key = s3_config.get_upload_key(filename)
    
    try:
        # Generate presigned URL
        upload_url = s3_service.generate_presigned_upload_url(s3_key, content_type)
        
        return {
            "job_id": job_id,
            "s3_key": s3_key,
            "upload_url": upload_url,
            "url_length": len(upload_url),
            "url_starts_with_https": upload_url.startswith('https://'),
            "content_type": content_type,
            "filename": filename,
            "user": user
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}")

@router.post("/upload/confirm")
async def confirm_upload(
    job_id: str = Form(...),
    s3_key: str = Form(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """Confirm successful upload and create processing job"""
    try:
        # Verify file exists in S3
        if not s3_service.file_exists(s3_key):
            raise HTTPException(status_code=404, detail="File not found in S3")
        
        # Get file metadata
        metadata = s3_service.get_file_metadata(s3_key)
        
        # Create Video record
        video = models.Video(
            filename=s3_key.split('/')[-1],  # Extract filename from S3 key
            owner=user["username"],
            s3_key=s3_key,
            s3_url=f"https://{s3_config.bucket_name}.s3.{s3_config.region}.amazonaws.com/{s3_key}"
        )
        db.add(video)
        db.commit()
        db.refresh(video)

        # Create Job record in RDS
        job = models.Job(
            job_id=job_id,
            video_id=video.id,
            status="queued",
            s3_input_key=s3_key
        )
        db.add(job)
        db.commit()

        # Create job progress record in DynamoDB
        dynamodb_service.create_job_progress(
            job_id=job_id,
            video_filename=s3_key.split('/')[-1],  # Extract filename from S3 key
            owner=user["username"]
        )

        # Dispatch processing job via SQS
        sqs_service.send_job_message(job_id, s3_key, user["username"])

        return {"job_id": job_id, "status": "queued"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload confirmation failed: {str(e)}")