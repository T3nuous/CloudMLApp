from pydantic import BaseModel
from typing import Optional, Any, List, Dict

class TokenResponse(BaseModel):
    access_token: str
    id_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[Dict[str, Any]] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str

class ConfirmRequest(BaseModel):
    username: str
    code: str

class JobCreateResponse(BaseModel):
    job_id: str

class JobStatus(BaseModel):
    job_id: str
    status: str
    result: Optional[Dict[str, Any]] = None

class VideoCreateResponse(BaseModel):
    video_id: int
    filename: str

class JobListResponse(BaseModel):
    jobs: List[JobStatus]
    page: int
    per_page: int
    total: int

class JobProgressResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    current_step: str
    total_steps: int
    steps: Dict[str, Any]
    created_at: str
    updated_at: str
    video_filename: str
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

class FileInfoResponse(BaseModel):
    job_id: str
    status: str
    created_at: str
    files: Dict[str, Any]
    ml_results: Optional[List[Dict[str, Any]]] = None

class MLResultsResponse(BaseModel):
    job_id: str
    ml_results: List[Dict[str, Any]]
    total_frames: int
