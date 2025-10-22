# app/dynamodb_service.py
import boto3
import json
from typing import Dict, Any, Optional, List
from botocore.exceptions import ClientError
from datetime import datetime
import os
from decimal import Decimal

class DynamoDBService:
    """Service for DynamoDB job progress operations"""
    
    def __init__(self, region: str = 'ap-southeast-2'):
        self.region = region
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table_name = os.environ.get('DYNAMODB_TABLE_NAME', 'n11086840-video-ml-job-progress')
        self.qut_username = os.environ.get('QUT_USERNAME', 'n11086840@qut.edu.au')
        self.table = self.dynamodb.Table(self.table_name)
    
    def _convert_floats_to_decimal(self, obj):
        """Convert float values to Decimal for DynamoDB compatibility"""
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {k: self._convert_floats_to_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_floats_to_decimal(item) for item in obj]
        else:
            return obj
    
    def create_job_progress(self, job_id: str, video_filename: str, owner: str) -> bool:
        """Create initial job progress record"""
        try:
            item = {
                'qut_username': self.qut_username,  # Partition key
                'job_id': job_id,  # Sort key
                'status': 'queued',
                'progress': 0,
                'current_step': 'initialized',
                'total_steps': 5,
                'created_at': datetime.utcnow().isoformat() + 'Z',
                'updated_at': datetime.utcnow().isoformat() + 'Z',
                'video_filename': video_filename,
                'owner': owner,
                'steps': {
                    '1': {'name': 'Download from S3', 'current_status': 'pending'},
                    '2': {'name': 'Extract thumbnail', 'current_status': 'pending'},
                    '3': {'name': 'Transcode video', 'current_status': 'pending'},
                    '4': {'name': 'ML prediction', 'current_status': 'pending'},
                    '5': {'name': 'Upload results', 'current_status': 'pending'}
                }
            }
            
            self.table.put_item(Item=item)
            print(f"✅ Created job progress for {job_id}")
            return True
            
        except ClientError as e:
            print(f"❌ Error creating job progress: {e}")
            return False
    
    def update_job_progress(self, job_id: str, progress: int, current_step: str, 
                          step_status: str = 'completed', result: Optional[Dict] = None) -> bool:
        """Update job progress"""
        try:
            # Start with basic updates only - avoid nested updates for now
            update_expression = "SET progress = :progress, current_step = :current_step, updated_at = :updated_at"
            expression_values = {
                ':progress': progress,
                ':current_step': current_step,
                ':updated_at': datetime.utcnow().isoformat() + 'Z'
            }
            expression_names = {}
            
            # Add ML result if provided
            if result:
                update_expression += ", ml_result = :ml_result"
                expression_values[':ml_result'] = self._convert_floats_to_decimal(result)
            
            # Build update parameters
            update_params = {
                'Key': {
                    'qut_username': self.qut_username,
                    'job_id': job_id
                },
                'UpdateExpression': update_expression,
                'ExpressionAttributeValues': expression_values
            }
            
            # Only add ExpressionAttributeNames if we have any
            if expression_names:
                update_params['ExpressionAttributeNames'] = expression_names
            
            self.table.update_item(**update_params)
            
            print(f"✅ Updated job progress for {job_id}: {progress}% - {current_step}")
            return True
            
        except ClientError as e:
            print(f"❌ Error updating job progress: {e}")
            return False
    
    def complete_job(self, job_id: str, result: Dict[str, Any]) -> bool:
        """Mark job as completed with final result"""
        try:
            self.table.update_item(
                Key={
                    'qut_username': self.qut_username,
                    'job_id': job_id
                },
                UpdateExpression="SET #status = :status, progress = :progress, ml_result = :ml_result, updated_at = :updated_at",
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'completed',
                    ':progress': 100,
                    ':ml_result': self._convert_floats_to_decimal(result),
                    ':updated_at': datetime.utcnow().isoformat() + 'Z'
                }
            )
            
            print(f"✅ Completed job {job_id}")
            return True
            
        except ClientError as e:
            print(f"❌ Error completing job: {e}")
            return False
    
    def fail_job(self, job_id: str, error_message: str) -> bool:
        """Mark job as failed with error message"""
        try:
            self.table.update_item(
                Key={
                    'qut_username': self.qut_username,
                    'job_id': job_id
                },
                UpdateExpression="SET #status = :status, error_message = :error_message, updated_at = :updated_at",
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'failed',
                    ':error_message': error_message,
                    ':updated_at': datetime.utcnow().isoformat() + 'Z'
                }
            )
            
            print(f"❌ Failed job {job_id}: {error_message}")
            return True
            
        except ClientError as e:
            print(f"❌ Error failing job: {e}")
            return False
    
    def get_job_progress(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job progress by job_id"""
        try:
            response = self.table.get_item(Key={
                'qut_username': self.qut_username,
                'job_id': job_id
            })
            return response.get('Item')
        except ClientError as e:
            print(f"❌ Error getting job progress: {e}")
            return None
    
    def list_jobs_by_status(self, status: str, limit: int = 50) -> List[Dict[str, Any]]:
        """List jobs by status using GSI"""
        try:
            response = self.table.query(
                IndexName='status-index',
                KeyConditionExpression='#status = :status',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={':status': status},
                Limit=limit,
                ScanIndexForward=False  # Most recent first
            )
            return response.get('Items', [])
        except ClientError as e:
            print(f"❌ Error listing jobs by status: {e}")
            return []
    
    def list_user_jobs(self, owner: str, limit: int = 50) -> List[Dict[str, Any]]:
        """List jobs for a specific user using QUT username partition"""
        try:
            response = self.table.query(
                KeyConditionExpression='qut_username = :qut_username',
                FilterExpression='owner = :owner',
                ExpressionAttributeValues={
                    ':qut_username': self.qut_username,
                    ':owner': owner
                },
                Limit=limit
            )
            return response.get('Items', [])
        except ClientError as e:
            print(f"❌ Error listing user jobs: {e}")
            return []
    
    def get_job_statistics(self) -> Dict[str, int]:
        """Get job statistics"""
        try:
            # Get counts by status
            statuses = ['queued', 'processing', 'completed', 'failed']
            stats = {}
            
            for status in statuses:
                jobs = self.list_jobs_by_status(status, limit=1000)
                stats[status] = len(jobs)
            
            return stats
        except Exception as e:
            print(f"❌ Error getting job statistics: {e}")
            return {}

# Global instance
dynamodb_service = DynamoDBService()
