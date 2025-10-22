from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from db import Base

# AWS TODO (Schema on RDS):
# - Run these SQLAlchemy models against RDS (Postgres/MySQL) instead of SQLite
# - Use migrations (Alembic) rather than Base.metadata.create_all in production
# - Ensure indices and constraints suit your expected workload

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_pw = Column(String)
    role = Column(String, default="user")

class Video(Base):
    __tablename__ = "videos"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    owner = Column(String, index=True)
    s3_key = Column(String, nullable=True)  # S3 key for uploaded file
    s3_url = Column(String, nullable=True)  # S3 URL for the file
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, unique=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=True)
    status = Column(String, default="queued")
    result = Column(JSON, nullable=True)
    s3_input_key = Column(String, nullable=True)  # S3 key for input file
    s3_output_key = Column(String, nullable=True)  # S3 key for transcoded output
    s3_thumbnail_key = Column(String, nullable=True)  # S3 key for thumbnail
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# AWS TODO (DynamoDB hybrid model):
# - Keep relational entities (User/Video/Job) in RDS
# - Store fast-changing or large, semi-structured items (e.g., per-frame inference) in DynamoDB keyed by job_id
# - Add a lightweight reference (e.g., a flag or pointer) in Job.result to indicate presence in DynamoDB

