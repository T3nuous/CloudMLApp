# app/routes/jobs.py
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from ..db import get_db
from .. import models
from ..schemas import JobListResponse, JobStatus, JobProgressResponse
from .dependencies import get_current_user
from ..dynamodb_service import dynamodb_service

router = APIRouter()

# AWS TODO (Status persistence & caching):
# - Persist fine-grained progress updates (e.g., percent complete) in DynamoDB keyed by job_id
# - Use Elasticache/Redis for caching JobStatus responses to reduce DB load on frequent polling
# - Consider publishing job state changes via SNS/SQS or WebSocket API Gateway for push notifications

def _result_for_user(result: Optional[Dict[str, Any]], role: str) -> Optional[Dict[str, Any]]:
    if result is None:
        return None
    if role == "admin":
        return result
    # non-admin: include safe fields but exclude ML results
    filtered = {}
    if result.get("transcoded"):
        filtered["transcoded"] = result["transcoded"]
    if result.get("thumbnail"):
        filtered["thumbnail"] = result["thumbnail"]
    if result.get("s3_outputs"):
        filtered["s3_outputs"] = result["s3_outputs"]
    return filtered if filtered else None

@router.get("/", response_model=JobListResponse)
def list_jobs(page: int = Query(1, ge=1), per_page: int = Query(10, ge=1, le=50),
              status: Optional[str] = None, owner: Optional[str] = None,
              db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    q = db.query(models.Job)
    if status:
        q = q.filter(models.Job.status == status)
    if owner:
        q = q.join(models.Video, models.Video.id == models.Job.video_id).filter(models.Video.owner == owner)

    total = q.count()
    items = q.order_by(models.Job.created_at.desc()).offset((page-1)*per_page).limit(per_page).all()

    jobs = []
    for it in items:
        safe = _result_for_user(it.result, user.get("role"))
        jobs.append(JobStatus(job_id=it.job_id, status=it.status, result=safe))
    return JobListResponse(jobs=jobs, page=page, per_page=per_page, total=total)

@router.get("/{job_id}", response_model=JobStatus)
def get_job(job_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    j = db.query(models.Job).filter(models.Job.job_id == job_id).first()
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")
    safe = _result_for_user(j.result, user.get("role"))
    return JobStatus(job_id=j.job_id, status=j.status, result=safe)

@router.get("/{job_id}/progress", response_model=JobProgressResponse)
def get_job_progress(job_id: str, user: dict = Depends(get_current_user)):
    """Get detailed job progress from DynamoDB"""
    try:
        progress_data = dynamodb_service.get_job_progress(job_id)
        if not progress_data:
            raise HTTPException(status_code=404, detail="Job progress not found")
        
        return {
            "job_id": job_id,
            "status": progress_data.get("status", "unknown"),
            "progress": progress_data.get("progress", 0),
            "current_step": progress_data.get("current_step", "unknown"),
            "total_steps": progress_data.get("total_steps", 5),
            "steps": progress_data.get("steps", {}),
            "created_at": progress_data.get("created_at"),
            "updated_at": progress_data.get("updated_at"),
            "video_filename": progress_data.get("video_filename"),
            "result": progress_data.get("result"),
            "error_message": progress_data.get("error_message")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get job progress: {str(e)}")

@router.get("/user/{username}/jobs")
def get_user_jobs(username: str, limit: int = Query(50, ge=1, le=100), 
                  user: dict = Depends(get_current_user)):
    """Get jobs for a specific user from DynamoDB"""
    try:
        # Only allow users to see their own jobs unless they're admin
        if user.get("username") != username and user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Access denied")
        
        jobs = dynamodb_service.list_user_jobs(username, limit)
        return {
            "username": username,
            "jobs": jobs,
            "count": len(jobs)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get user jobs: {str(e)}")

@router.get("/status/{status}")
def get_jobs_by_status(status: str, limit: int = Query(50, ge=1, le=100),
                       user: dict = Depends(get_current_user)):
    """Get jobs by status from DynamoDB (admin only)"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        jobs = dynamodb_service.list_jobs_by_status(status, limit)
        return {
            "status": status,
            "jobs": jobs,
            "count": len(jobs)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get jobs by status: {str(e)}")

@router.get("/statistics/overview")
def get_job_statistics(user: dict = Depends(get_current_user)):
    """Get job statistics from DynamoDB (admin only)"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        stats = dynamodb_service.get_job_statistics()
        return {
            "statistics": stats,
            "total_jobs": sum(stats.values())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get job statistics: {str(e)}")

