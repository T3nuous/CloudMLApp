# app/tasks.py
import os
import json
import subprocess
import shutil
import traceback
import tempfile
from PIL import Image
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError

import torch
from torchvision import models
from torchvision.models import MobileNet_V2_Weights

_MODEL = None
_PREPROCESS = None
_LABELS_MAP = None

# AWS TODO (Stateless processing & storage):
# - Prefer S3 for inputs/outputs and EFS for shared temp if needed; avoid relying on local disk.
# - Accept S3 URIs (s3://bucket/key) for input_path and write outputs to S3 under a job-specific prefix.
# - Publish job progress to DynamoDB (or queue events via SQS/SNS) so any worker can resume.
# - Ensure idempotency: check for existing outputs before recomputing; handle retries.
# - Consider running workers on ECS/EKS/Batch for horizontal scaling.

def _ensure_model():
    global _MODEL, _PREPROCESS, _LABELS_MAP
    if _MODEL is None:
        weights = MobileNet_V2_Weights.IMAGENET1K_V1
        _MODEL = models.mobilenet_v2(weights=weights)
        _MODEL.eval()
        _PREPROCESS = weights.transforms()
        _LABELS_MAP = weights.meta.get("categories", None)
    return True

def transcode_video(input_path: str, output_path: str):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found in PATH")
    # High CPU load settings: higher resolution, slower preset, better quality
    cmd = [ffmpeg, "-y", "-i", input_path, 
           "-vf", "scale=1920:1080",  # 1080p instead of 720p
           "-c:v", "libx264", 
           "-preset", "slow",  # Much more CPU intensive than "fast"
           "-crf", "18",  # High quality (lower = better quality, more CPU)
           "-profile:v", "high",  # High profile encoding
           "-level", "4.1",  # Higher level encoding
           "-bf", "3",  # More B-frames (more CPU)
           "-g", "60",  # GOP size
           "-keyint_min", "60",  # Keyframe interval
           "-sc_threshold", "0",  # Scene change detection
           "-tune", "film",  # Film tuning for better quality
           "-x264opts", "ref=6:me=umh:subme=9:merange=24:trellis=2:aq-mode=3",  # Advanced encoding options
           output_path]
    subprocess.run(cmd, check=True)

def extract_frames(video_path: str, frames_dir: str, fps: int = 1):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found in PATH")
    os.makedirs(frames_dir, exist_ok=True)
    pattern = os.path.join(frames_dir, "frame_%05d.jpg")
    cmd = [ffmpeg, "-y", "-i", video_path, "-vf", f"fps={fps}", pattern]
    subprocess.run(cmd, check=True)

def run_inference_on_frames(frames_dir: str, topk: int = 3):
    results = []
    if _ensure_model():
        for fname in sorted(os.listdir(frames_dir)):
            if not fname.lower().endswith(".jpg"):
                continue
            path = os.path.join(frames_dir, fname)
            try:
                img = Image.open(path).convert("RGB")
                inp = _PREPROCESS(img).unsqueeze(0)
                with torch.no_grad():
                    out = _MODEL(inp)
                    probs = torch.nn.functional.softmax(out[0], dim=0)
                    top = torch.topk(probs, topk)
                    indices = top.indices.tolist()
                    values = top.values.tolist()
                    labels = []
                    for idx, p in zip(indices, values):
                        label_text = _LABELS_MAP[idx] if _LABELS_MAP else str(idx)
                        labels.append({"index": idx, "label": label_text, "probability": float(p)})
                    results.append({"frame": fname, "labels": labels})
            except Exception as e:
                results.append({"frame": fname, "labels": [{"error": str(e)}]})
    return results

def process_job(video_path: str, out_dir: str, fps: int = 1) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    transcoded = os.path.join(out_dir, "transcoded.mp4")
    frames_dir = os.path.join(out_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    # AWS TODO: If input is on S3, either stream or stage to EFS/tmp before transcoding.
    # Transcode
    transcode_video(video_path, transcoded)

    # Extract frames
    extract_frames(transcoded, frames_dir, fps=fps)

    # Inference
    inference = []
    try:
        inference = run_inference_on_frames(frames_dir, topk=3)
    except Exception as e:
        inference = [{"error": str(e), "trace": traceback.format_exc()}]

    # Thumbnail
    thumbnail_path = None
    thumbs = sorted([f for f in os.listdir(frames_dir) if f.lower().endswith(".jpg")])
    if thumbs:
        first = os.path.join(frames_dir, thumbs[0])
        thumbnail_path = os.path.join(out_dir, "thumbnail.jpg")
        img = Image.open(first)
        img.thumbnail((320, 180))
        img.save(thumbnail_path, "JPEG")

    result = {
        "transcoded": os.path.basename(transcoded) if os.path.exists(transcoded) else None,
        "thumbnail": os.path.basename(thumbnail_path) if thumbnail_path else None,
        "frames_dir": frames_dir,
        "inference": inference
    }

    # AWS TODO: Upload outputs (transcoded.mp4, frames, thumbnail, result.json) to S3 using SSE.
    # Save result for inspection
    try:
        with open(os.path.join(out_dir, "result.json"), "w") as f:
            json.dump(result, f)
    except Exception:
        pass

    return result

def process_job_s3(s3_input_key: str, job_id: str, fps: int = 1) -> dict:
    """Process video job with S3 input/output"""
    from s3_service import s3_service
    from s3_config import s3_config
    from dynamodb_service import DynamoDBService
    
    # Initialize DynamoDB service for progress tracking
    dynamodb_service = DynamoDBService()
    
    # Create temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Update progress: Download from S3
            dynamodb_service.update_job_progress(job_id, 20, "download", "Downloading video from S3...")
            
            # Download input video from S3
            input_video_path = os.path.join(temp_dir, "input_video.mp4")
            video_data = s3_service.download_file(s3_input_key)
            with open(input_video_path, "wb") as f:
                f.write(video_data)
            
            # Update progress: Extract thumbnail
            dynamodb_service.update_job_progress(job_id, 40, "thumbnail", "Extracting thumbnail...")
            
            # Process video
            result = process_job(input_video_path, temp_dir, fps)
            
            # Update progress: Transcode video
            dynamodb_service.update_job_progress(job_id, 60, "transcode", "Transcoding video...")
            
            # Update progress: ML prediction
            dynamodb_service.update_job_progress(job_id, 80, "ml_prediction", "Running ML predictions...")
            
            # Upload outputs to S3
            s3_outputs = {}
            
            # Upload transcoded video
            if result.get("transcoded"):
                transcoded_path = os.path.join(temp_dir, result["transcoded"])
                if os.path.exists(transcoded_path):
                    transcoded_key = s3_config.get_transcoded_key(job_id, result["transcoded"])
                    with open(transcoded_path, "rb") as f:
                        upload_result = s3_service.upload_file(f, transcoded_key, "video/mp4")
                        s3_outputs["transcoded"] = {
                            "key": transcoded_key,
                            "url": upload_result["url"]
                        }
            
            # Upload thumbnail
            if result.get("thumbnail"):
                thumbnail_path = os.path.join(temp_dir, result["thumbnail"])
                if os.path.exists(thumbnail_path):
                    thumbnail_key = s3_config.get_thumbnail_key(job_id, result["thumbnail"])
                    with open(thumbnail_path, "rb") as f:
                        upload_result = s3_service.upload_file(f, thumbnail_key, "image/jpeg")
                        s3_outputs["thumbnail"] = {
                            "key": thumbnail_key,
                            "url": upload_result["url"]
                        }
            
            # Upload frames (if needed for debugging)
            frames_dir = result.get("frames_dir")
            if frames_dir and os.path.exists(frames_dir):
                frame_files = [f for f in os.listdir(frames_dir) if f.lower().endswith(".jpg")]
                s3_outputs["frames"] = []
                for frame_file in frame_files[:5]:  # Limit to first 5 frames
                    frame_path = os.path.join(frames_dir, frame_file)
                    frame_key = s3_config.get_temp_key(job_id, f"frames/{frame_file}")
                    with open(frame_path, "rb") as f:
                        upload_result = s3_service.upload_file(f, frame_key, "image/jpeg")
                        s3_outputs["frames"].append({
                            "filename": frame_file,
                            "key": frame_key,
                            "url": upload_result["url"]
                        })
            
            # Add S3 outputs to result
            result["s3_outputs"] = s3_outputs
            
            # Upload result.json to S3
            result_key = s3_config.get_temp_key(job_id, "result.json")
            result_json = json.dumps(result, indent=2)
            result_bytes = result_json.encode('utf-8')
            from io import BytesIO
            s3_service.upload_file(BytesIO(result_bytes), result_key, "application/json")
            
            # Update progress: Upload results - COMPLETE
            dynamodb_service.update_job_progress(job_id, 100, "complete", "Job completed successfully!")
            dynamodb_service.complete_job(job_id, result)
            
            # Also update SQL database for API endpoints
            try:
                import json as json_lib  # Use alias to avoid shadowing global json
                from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, ForeignKey
                from sqlalchemy.orm import sessionmaker, declarative_base
                from sqlalchemy.sql import func
                import boto3
                
                # Create Base class directly
                Base = declarative_base()
                
                # Define Job model locally (without foreign key to avoid table dependency)
                class Job(Base):
                    __tablename__ = "jobs"
                    id = Column(Integer, primary_key=True, index=True)
                    job_id = Column(String, unique=True, index=True)
                    video_id = Column(Integer, nullable=True)  # Remove foreign key constraint
                    status = Column(String, default="queued")
                    result = Column(JSON, nullable=True)
                    s3_input_key = Column(String, nullable=True)
                    s3_output_key = Column(String, nullable=True)
                    s3_thumbnail_key = Column(String, nullable=True)
                    created_at = Column(DateTime(timezone=True), server_default=func.now())
                
                # Get database URL using same approach as main app
                database_url = None
                
                # Try environment variable first
                if os.environ.get("DATABASE_URL"):
                    database_url = os.environ.get("DATABASE_URL")
                    print(f"🔗 Using DATABASE_URL from environment")
                
                # Try AWS Secrets Manager
                if not database_url:
                    try:
                        secrets_client = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'ap-southeast-2'))
                        secret_name = os.environ.get('DB_SECRET_NAME', 'n11086840-Assessment2-Secret')
                        
                        response = secrets_client.get_secret_value(SecretId=secret_name)
                        secret = json_lib.loads(response['SecretString'])
                        
                        database_url = f"postgresql+psycopg2://{secret['username']}:{secret['password']}@{secret['host']}:{secret['port']}/{secret['dbname']}?sslmode=require"
                        print(f"🔗 Using database URL from Secrets Manager")
                    except Exception as e:
                        print(f"⚠️ Could not get DB config from Secrets Manager: {e}")
                
                # Fallback to individual environment variables
                if not database_url:
                    host = os.environ.get('RDS_HOST', 'database-1-instance-1.ce2haupt2cta.ap-southeast-2.rds.amazonaws.com')
                    port = os.environ.get('RDS_PORT', '5432')
                    database = os.environ.get('RDS_DB_NAME', 'cohort_2025')
                    username = os.environ.get('RDS_USERNAME', '')
                    password = os.environ.get('RDS_PASSWORD', '')
                    
                    if username and password:
                        database_url = f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{database}?sslmode=require"
                        print(f"🔗 Using database URL from environment variables")
                    else:
                        print(f"⚠️ No database credentials available, skipping SQL update")
                        return result
                
                # Create database connection
                engine = create_engine(database_url)
                SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
                db = SessionLocal()
                print(f"🔗 Database connection created successfully")
                
                # Update job in SQL database
                print(f"🔍 Looking for job {job_id} in SQL database...")
                job = db.query(Job).filter(Job.job_id == job_id).first()
                if job:
                    print(f"🔍 Found job {job_id} with status: {job.status}")
                    job.status = "done"
                    job.result = result
                    db.commit()
                    print(f"✅ Updated SQL database for job {job_id}")
                else:
                    print(f"⚠️ Job {job_id} not found in SQL database")
                    # List all jobs for debugging
                    all_jobs = db.query(Job).all()
                    print(f"🔍 Available jobs: {[j.job_id for j in all_jobs]}")
                
                db.close()
                    
            except Exception as sql_error:
                print(f"⚠️ Failed to update SQL database: {sql_error}")
                import traceback
                traceback.print_exc()
            
            return result
            
        except Exception as e:
            print(f"Error processing job {job_id}: {e}")
            traceback.print_exc()
            
            # Update DynamoDB with error status
            try:
                dynamodb_service.update_job_progress(job_id, 0, "error", f"Job failed: {str(e)}")
                dynamodb_service.fail_job(job_id, str(e))
            except Exception as db_error:
                print(f"Failed to update DynamoDB with error status: {db_error}")
            
            return {
                "error": str(e),
                "trace": traceback.format_exc(),
                "s3_input_key": s3_input_key
            }