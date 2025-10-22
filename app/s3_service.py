# app/s3_service.py
import boto3
import json
from typing import Optional, Dict, Any, BinaryIO
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import HTTPException
from s3_config import s3_config
import mimetypes
import os

class S3Service:
    """Service for AWS S3 operations"""
    
    def __init__(self):
        try:
            self.s3_client = boto3.client('s3', region_name=s3_config.region)
            self.s3_resource = boto3.resource('s3', region_name=s3_config.region)
        except NoCredentialsError:
            raise HTTPException(status_code=500, detail="AWS credentials not found")
    
    def create_bucket(self) -> bool:
        """Create S3 bucket if it doesn't exist"""
        try:
            # Check if bucket exists
            self.s3_client.head_bucket(Bucket=s3_config.bucket_name)
            print(f"Bucket {s3_config.bucket_name} already exists")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                # Bucket doesn't exist, create it
                try:
                    if s3_config.region == 'us-east-1':
                        # us-east-1 doesn't need LocationConstraint
                        response = self.s3_client.create_bucket(Bucket=s3_config.bucket_name)
                    else:
                        response = self.s3_client.create_bucket(
                            Bucket=s3_config.bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': s3_config.region}
                        )
                    print(f"Bucket {s3_config.bucket_name} created successfully")
                    
                    # Configure bucket
                    self._configure_bucket()
                    return True
                except ClientError as create_error:
                    print(f"Error creating bucket: {create_error}")
                    return False
            else:
                print(f"Error checking bucket: {e}")
                return False
    
    def _configure_bucket(self):
        """Configure bucket with CORS, policy, and tags"""
        try:
            # Set CORS configuration
            self.s3_client.put_bucket_cors(
                Bucket=s3_config.bucket_name,
                CORSConfiguration=s3_config.cors_configuration
            )
            print("CORS configuration set")
            
            # Set bucket policy
            self.s3_client.put_bucket_policy(
                Bucket=s3_config.bucket_name,
                Policy=json.dumps(s3_config.bucket_policy)
            )
            print("Bucket policy set")
            
            # Tag the bucket
            self.s3_client.put_bucket_tagging(
                Bucket=s3_config.bucket_name,
                Tagging={'TagSet': [{'Key': k, 'Value': v} for k, v in s3_config.tags.items()]}
            )
            print("Bucket tagged")
            
        except ClientError as e:
            print(f"Error configuring bucket: {e}")
    
    def upload_file(self, file_obj: BinaryIO, key: str, content_type: Optional[str] = None) -> Dict[str, Any]:
        """Upload file to S3"""
        try:
            # Determine content type if not provided
            if not content_type:
                content_type, _ = mimetypes.guess_type(key)
                if not content_type:
                    content_type = 'application/octet-stream'
            
            # Upload file
            extra_args = {
                'ContentType': content_type,
                'ServerSideEncryption': 'AES256'
            }
            
            self.s3_client.upload_fileobj(
                file_obj,
                s3_config.bucket_name,
                key,
                ExtraArgs=extra_args
            )
            
            # Get object URL
            object_url = f"https://{s3_config.bucket_name}.s3.{s3_config.region}.amazonaws.com/{key}"
            
            return {
                'success': True,
                'key': key,
                'url': object_url,
                'bucket': s3_config.bucket_name
            }
            
        except ClientError as e:
            print(f"Error uploading file: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")
    
    def download_file(self, key: str) -> bytes:
        """Download file from S3"""
        try:
            response = self.s3_client.get_object(Bucket=s3_config.bucket_name, Key=key)
            return response['Body'].read()
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise HTTPException(status_code=404, detail="File not found")
            raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")
    
    def generate_presigned_url(self, key: str, operation: str = 'get_object', 
                             expires_in: Optional[int] = None) -> str:
        """Generate pre-signed URL for S3 object"""
        try:
            if expires_in is None:
                expires_in = s3_config.presigned_url_expiry
            
            response = self.s3_client.generate_presigned_url(
                operation,
                Params={'Bucket': s3_config.bucket_name, 'Key': key},
                ExpiresIn=expires_in
            )
            return response
        except ClientError as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate pre-signed URL: {str(e)}")
    
    def generate_presigned_upload_url(self, key: str, content_type: str, 
                                    expires_in: Optional[int] = None) -> str:
        """Generate pre-signed URL for uploading to S3"""
        try:
            if expires_in is None:
                expires_in = s3_config.presigned_url_expiry
            
            # Generate presigned URL with ContentType parameter
            response = self.s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': s3_config.bucket_name,
                    'Key': key,
                    'ContentType': content_type
                },
                ExpiresIn=expires_in
            )
            return response
        except ClientError as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate upload URL: {str(e)}")
    
    def delete_file(self, key: str) -> bool:
        """Delete file from S3"""
        try:
            self.s3_client.delete_object(Bucket=s3_config.bucket_name, Key=key)
            return True
        except ClientError as e:
            print(f"Error deleting file: {e}")
            return False
    
    def list_files(self, prefix: str = "", max_keys: int = 1000) -> list:
        """List files in S3 bucket with optional prefix"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=s3_config.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            return response.get('Contents', [])
        except ClientError as e:
            print(f"Error listing files: {e}")
            return []
    
    def file_exists(self, key: str) -> bool:
        """Check if file exists in S3"""
        try:
            self.s3_client.head_object(Bucket=s3_config.bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise HTTPException(status_code=500, detail=f"Error checking file existence: {str(e)}")
    
    def get_file_metadata(self, key: str) -> Dict[str, Any]:
        """Get file metadata from S3"""
        try:
            response = self.s3_client.head_object(Bucket=s3_config.bucket_name, Key=key)
            return {
                'content_type': response.get('ContentType'),
                'content_length': response.get('ContentLength'),
                'last_modified': response.get('LastModified'),
                'etag': response.get('ETag'),
                'metadata': response.get('Metadata', {})
            }
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                raise HTTPException(status_code=404, detail="File not found")
            raise HTTPException(status_code=500, detail=f"Error getting file metadata: {str(e)}")
    
    def copy_file(self, source_key: str, dest_key: str) -> bool:
        """Copy file within S3 bucket"""
        try:
            copy_source = {
                'Bucket': s3_config.bucket_name,
                'Key': source_key
            }
            self.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=s3_config.bucket_name,
                Key=dest_key
            )
            return True
        except ClientError as e:
            print(f"Error copying file: {e}")
            return False

# Global service instance
s3_service = S3Service()
