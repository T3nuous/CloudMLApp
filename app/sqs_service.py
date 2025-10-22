import boto3
import json
from datetime import datetime
from typing import Dict, Any, List

class SQSService:
    def __init__(self):
        self.sqs = boto3.client('sqs', region_name='ap-southeast-2')
        self.queue_url = "https://sqs.ap-southeast-2.amazonaws.com/901444280953/n11086840-video-processing-queue"
    
    def send_job_message(self, job_id: str, s3_key: str, user: str) -> Dict[str, Any]:
        message = {
            "job_id": job_id,
            "s3_key": s3_key,
            "user": user,
            "timestamp": str(datetime.utcnow())
        }
        
        response = self.sqs.send_message(
            QueueUrl=self.queue_url,
            MessageBody=json.dumps(message)
        )
        return response
    
    def receive_messages(self, max_messages: int = 10) -> List[Dict]:
        response = self.sqs.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=20
        )
        return response.get('Messages', [])
    
    def delete_message(self, receipt_handle: str):
        self.sqs.delete_message(
            QueueUrl=self.queue_url,
            ReceiptHandle=receipt_handle
        )