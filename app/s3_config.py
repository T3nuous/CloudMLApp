# app/s3_config.py
import os
from typing import Dict, Any

class S3Config:
    """Configuration for AWS S3 bucket operations"""
    
    def __init__(self):
        # S3 Configuration
        self.region = os.getenv("AWS_REGION", "ap-southeast-2")
        self.bucket_name = os.getenv("S3_BUCKET_NAME", "n11086840-video-ml-transcode-bucket")
        
        # Bucket paths for different content types
        self.upload_prefix = os.getenv("S3_UPLOAD_PREFIX", "uploads/")
        self.transcoded_prefix = os.getenv("S3_TRANSCODED_PREFIX", "transcoded/")
        self.thumbnails_prefix = os.getenv("S3_THUMBNAILS_PREFIX", "thumbnails/")
        self.temp_prefix = os.getenv("S3_TEMP_PREFIX", "temp/")
        
        # Pre-signed URL settings
        self.presigned_url_expiry = int(os.getenv("S3_PRESIGNED_URL_EXPIRY", "3600"))  # 1 hour
        
        # CORS configuration for web uploads
        self.cors_configuration = {
            'CORSRules': [
                {
                    'AllowedHeaders': ['*'],
                    'AllowedMethods': ['GET', 'PUT', 'POST', 'DELETE', 'HEAD'],
                    'AllowedOrigins': ['*'],
                    'ExposeHeaders': ['ETag'],
                    'MaxAgeSeconds': 3000
                }
            ]
        }
        
        # Bucket policy for public read access to transcoded videos
        self.bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicReadGetObject",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{self.bucket_name}/transcoded/*"
                }
            ]
        }
        
        # Tags for the bucket
        self.tags = {
            'qut-username': os.getenv("QUT_USERNAME", "your-username@qut.edu.au"),
            'purpose': 'video-ml-transcode',
            'environment': os.getenv("ENVIRONMENT", "development"),
            'project': 'video-ml-api'
        }
    
    def get_upload_key(self, filename: str) -> str:
        """Generate S3 key for uploaded files"""
        import uuid
        unique_id = str(uuid.uuid4())
        return f"{self.upload_prefix}{unique_id}_{filename}"
    
    def get_transcoded_key(self, job_id: str, filename: str) -> str:
        """Generate S3 key for transcoded files"""
        return f"{self.transcoded_prefix}{job_id}/{filename}"
    
    def get_thumbnail_key(self, job_id: str, filename: str = "thumbnail.jpg") -> str:
        """Generate S3 key for thumbnail files"""
        return f"{self.thumbnails_prefix}{job_id}/{filename}"
    
    def get_temp_key(self, job_id: str, filename: str) -> str:
        """Generate S3 key for temporary files"""
        return f"{self.temp_prefix}{job_id}/{filename}"

# Global config instance
s3_config = S3Config()
