# app/routes/videos.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse, FileResponse
from sqlalchemy.orm import Session
from .dependencies import get_current_user, admin_required
from .. import utils, models
from ..db import get_db
from ..s3_service import s3_service
from ..s3_config import s3_config
from ..schemas import FileInfoResponse, MLResultsResponse
import os

router = APIRouter()

# AWS TODO (S3 presigned downloads):
# - Replace server-side file responses with S3 pre-signed GET URLs
# - Validate authorization, then return a time-limited URL to the client
# - If streaming via server, stream from S3 to client to avoid storing files locally

# Any user may download the transcoded video
@router.get("/download/{job_id}")
def download_transcoded(job_id: str, db: Session = Depends(get_db)):
    """Download transcoded video via S3 pre-signed URL"""
    # Get job from database
    job = db.query(models.Job).filter(models.Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check if job is completed
    if job.status != "done":
        raise HTTPException(status_code=400, detail="Job not completed yet")
    
    # Get S3 output key from job result
    if not job.result or "s3_outputs" not in job.result:
        raise HTTPException(status_code=404, detail="Transcoded file not available")
    
    s3_outputs = job.result["s3_outputs"]
    if "transcoded" not in s3_outputs:
        raise HTTPException(status_code=404, detail="Transcoded file not available")
    
    transcoded_info = s3_outputs["transcoded"]
    s3_key = transcoded_info["key"]
    
    # Generate pre-signed URL for download
    try:
        download_url = s3_service.generate_presigned_url(s3_key, "get_object")
        return RedirectResponse(url=download_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate download URL: {str(e)}")

# Thumbnail (admin-only)
@router.get("/thumbnail/{job_id}")
def download_thumbnail(job_id: str, user: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Download thumbnail via S3 pre-signed URL"""
    # Get job from database
    job = db.query(models.Job).filter(models.Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check if job is completed
    if job.status != "done":
        raise HTTPException(status_code=400, detail="Job not completed yet")
    
    # Get S3 output key from job result
    if not job.result or "s3_outputs" not in job.result:
        raise HTTPException(status_code=404, detail="Thumbnail not available")
    
    s3_outputs = job.result["s3_outputs"]
    if "thumbnail" not in s3_outputs:
        raise HTTPException(status_code=404, detail="Thumbnail not available")
    
    thumbnail_info = s3_outputs["thumbnail"]
    s3_key = thumbnail_info["key"]
    
    # Generate pre-signed URL for download
    try:
        download_url = s3_service.generate_presigned_url(s3_key, "get_object")
        return RedirectResponse(url=download_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate thumbnail URL: {str(e)}")

# Get file info
@router.get("/info/{job_id}", response_model=FileInfoResponse)
def get_file_info(job_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get file information and URLs"""
    # Get job from database
    job = db.query(models.Job).filter(models.Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    result = {
        "job_id": job_id,
        "status": job.status,
        "created_at": str(job.created_at),
        "files": {},
        "ml_results": None
    }
    
    if job.status == "done" and job.result and "s3_outputs" in job.result:
        s3_outputs = job.result["s3_outputs"]
        
        # Generate pre-signed URLs for available files
        for file_type, file_info in s3_outputs.items():
            if isinstance(file_info, dict) and "key" in file_info:
                try:
                    download_url = s3_service.generate_presigned_url(file_info["key"], "get_object")
                    result["files"][file_type] = {
                        "url": download_url,
                        "s3_key": file_info["key"]
                    }
                except Exception as e:
                    result["files"][file_type] = {
                        "error": f"Failed to generate URL: {str(e)}",
                        "s3_key": file_info["key"]
                    }
        
        # Include ML results if available (admin only)
        if "inference" in job.result and user.get("role") == "admin":
            result["ml_results"] = job.result["inference"]
    
    return result

@router.get("/results/{job_id}", response_model=MLResultsResponse)
def get_ml_results(job_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get ML inference results for a job (admin only)"""
    # Check if user is admin
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required for ML results")
    
    # Get job from database
    job = db.query(models.Job).filter(models.Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != "done":
        raise HTTPException(status_code=400, detail="Job not completed yet")
    
    if not job.result or "inference" not in job.result:
        raise HTTPException(status_code=404, detail="ML results not available")
    
    return {
        "job_id": job_id,
        "ml_results": job.result["inference"],
        "total_frames": len(job.result["inference"]) if job.result["inference"] else 0
    }
