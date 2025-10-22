import json
import sys
import os

# Change to the app directory
os.chdir('/app')

# Add the app directory to Python path
sys.path.insert(0, '/app')

from sqs_service import SQSService
from tasks import process_job_s3

def main():
    print("🚀 Starting Video Processing Worker...")
    print(f"Current directory: {os.getcwd()}")
    print(f"Python path: {sys.path[:3]}")
    
    sqs_service = SQSService()
    
    while True:
        messages = sqs_service.receive_messages()
        for message in messages:
            try:
                body = json.loads(message['Body'])
                job_id = body['job_id']
                s3_key = body['s3_key']
                
                print(f"📥 Processing job: {job_id}")
                
                # Process the job
                result = process_job_s3(s3_key, job_id, 1)
                
                print(f"✅ Job completed: {job_id}")
                
                # Delete message after successful processing
                sqs_service.delete_message(message['ReceiptHandle'])
                
            except Exception as e:
                print(f"❌ Error processing message: {e}")
                import traceback
                traceback.print_exc()
                # Message will be retried or sent to DLQ

if __name__ == "__main__":
    main()