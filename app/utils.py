import os
import uuid

DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
os.makedirs(DATA_DIR, exist_ok=True)

# AWS TODO (S3 integration):
# - Replace local filesystem paths with S3 object keys and buckets
# - Use boto3 S3 client/resource for uploads and downloads
# - Generate pre-signed URLs for client direct upload/download
#   * upload: server returns PUT pre-signed URL; client uploads file to S3
#   * download: server returns GET pre-signed URL (or streams via server)
# - Store bucket name in env var (e.g., S3_BUCKET) sourced from SSM Parameter Store

def make_job_id() -> str:
    return str(uuid.uuid4())

def video_save_path(job_id: str, filename: str) -> str:
    base = os.path.join(DATA_DIR, "uploads")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f"{job_id}_{filename}")

def job_out_dir(job_id: str) -> str:
    out = os.path.join(DATA_DIR, "jobs", job_id)
    os.makedirs(out, exist_ok=True)
    return out

# AWS TODO (EFS option):
# - If large intermediate files are needed across instances, mount EFS and repoint DATA_DIR to EFS mount path
# - Alternatively prefer S3 for artifacts to keep app stateless