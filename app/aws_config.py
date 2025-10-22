#!/usr/bin/env python3
"""
AWS Configuration Helper
Loads configuration from SSM Parameter Store and Secrets Manager
"""

import os
import boto3
import json
from botocore.exceptions import ClientError
from typing import Dict, Any, Optional

class AWSConfig:
    """Centralized AWS configuration management"""
    
    def __init__(self, region: str = 'ap-southeast-2'):
        self.region = region
        self.ssm_client = boto3.client('ssm', region_name=region)
        self.secrets_client = boto3.client('secretsmanager', region_name=region)
        
    def get_ssm_parameter(self, parameter_name: str, default_value: str = None) -> str:
        """Get parameter from SSM Parameter Store"""
        try:
            response = self.ssm_client.get_parameter(
                Name=parameter_name,
                WithDecryption=True
            )
            return response['Parameter']['Value']
        except ClientError as e:
            if e.response['Error']['Code'] == 'ParameterNotFound':
                print(f"⚠️  SSM parameter {parameter_name} not found, using default: {default_value}")
                return default_value
            else:
                print(f"❌ Error getting SSM parameter {parameter_name}: {e}")
                return default_value
    
    def get_secret(self, secret_name: str) -> Dict[str, Any]:
        """Get secret from Secrets Manager"""
        try:
            response = self.secrets_client.get_secret_value(SecretId=secret_name)
            return json.loads(response['SecretString'])
        except ClientError as e:
            print(f"❌ Error getting secret {secret_name}: {e}")
            return {}
    
    def load_configuration(self) -> Dict[str, Any]:
        """Load all configuration from AWS services"""
        config = {
            # SSM Parameters (student scoped)
            'api_base_url': self.get_ssm_parameter('/n11086840/video-ml-app/api-base-url', 'http://localhost:8000'),
            's3_bucket': self.get_ssm_parameter('/n11086840/video-ml-app/s3-bucket', 'video-ml-transcode-bucket'),
            'cognito_region': self.get_ssm_parameter('/n11086840/video-ml-app/cognito-region', 'ap-southeast-2'),
            'cognito_user_pool_id': self.get_ssm_parameter('/n11086840/video-ml-app/cognito-user-pool-id', 'ap-southeast-2_Z0cUimBcQ'),
            'cognito_client_id': self.get_ssm_parameter('/n11086840/video-ml-app/cognito-client-id', '2tlsiqgfi8uk4h5s2kj4ajbp9b'),
            
            # Secrets Manager
            'db_credentials': self.get_secret(os.getenv('DB_SECRET_NAME', 'n11086840-Assessment2-Secret')),
            
            # Environment variables (fallback)
            'qut_username': os.getenv('QUT_USERNAME', 'n11086840@qut.edu.au'),
            'aws_region': os.getenv('AWS_REGION', 'ap-southeast-2'),
            'dynamodb_table': os.getenv('DYNAMODB_TABLE_NAME', 'n11086840-video-ml-job-progress'),
        }
        
        return config
    
    def setup_environment_variables(self):
        """Set environment variables from AWS configuration"""
        config = self.load_configuration()
        
        # Set environment variables for the application
        os.environ['API_BASE_URL'] = config['api_base_url']
        os.environ['S3_BUCKET_NAME'] = config['s3_bucket']
        os.environ['COGNITO_REGION'] = config['cognito_region']
        os.environ['COGNITO_USER_POOL_ID'] = config['cognito_user_pool_id']
        os.environ['COGNITO_CLIENT_ID'] = config['cognito_client_id']
        os.environ['QUT_USERNAME'] = config['qut_username']
        os.environ['AWS_REGION'] = config['aws_region']
        os.environ['DYNAMODB_TABLE_NAME'] = config['dynamodb_table']
        
        # Set database URL from secrets
        if config['db_credentials']:
            db_creds = config['db_credentials']
            database_url = f"postgresql+psycopg2://{db_creds['username']}:{db_creds['password']}@{db_creds['host']}:{db_creds['port']}/{db_creds['dbname']}"
            os.environ['DATABASE_URL'] = database_url
            print(f"✅ Database URL configured from Secrets Manager")
        else:
            print("⚠️  Using fallback database configuration")
        
        print("✅ AWS configuration loaded successfully")
        return config

# Global config instance
aws_config = AWSConfig()

def load_aws_config():
    """Load AWS configuration and set environment variables"""
    return aws_config.setup_environment_variables()

if __name__ == "__main__":
    # Test configuration loading
    config = load_aws_config()
    print("\n📋 Loaded Configuration:")
    for key, value in config.items():
        if key == 'db_credentials' and value:
            print(f"  {key}: {list(value.keys())} (credentials loaded)")
        else:
            print(f"  {key}: {value}")
