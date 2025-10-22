from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
import boto3
import json
from botocore.exceptions import ClientError

def get_database_url() -> str:
    """Get database URL from environment or AWS Secrets Manager"""
    # Try environment variable first
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return database_url
    
    # Try to get from AWS Secrets Manager
    try:
        secrets_client = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'ap-southeast-2'))
        # Accept either a secret name or a full ARN via DB_SECRET_NAME; default to student secret name
        secret_name = os.environ.get('DB_SECRET_NAME', 'n11086840-Assessment2-Secret')
        
        response = secrets_client.get_secret_value(SecretId=secret_name)
        secret = json.loads(response['SecretString'])
        
        # Construct PostgreSQL URL with SSL requirement
        return f"postgresql+psycopg2://{secret['username']}:{secret['password']}@{secret['host']}:{secret['port']}/{secret['dbname']}?sslmode=require"
    except Exception as e:
        print(f"⚠️  Could not get DB config from Secrets Manager: {e}")
        print("Falling back to environment variables...")
        
        # Fallback to individual environment variables for shared database
        host = os.environ.get('RDS_HOST', 'database-1-instance-1.ce2haupt2cta.ap-southeast-2.rds.amazonaws.com')
        port = os.environ.get('RDS_PORT', '5432')
        database = os.environ.get('RDS_DB_NAME', 'cohort_2025')
        username = os.environ.get('RDS_USERNAME', '')  # Will be provided via Canvas
        password = os.environ.get('RDS_PASSWORD', '')  # Will be provided via Canvas
        
        # Check if credentials are provided
        if not username or not password:
            raise ValueError("RDS_USERNAME and RDS_PASSWORD environment variables must be set for shared database connection")
        
        return f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{database}?sslmode=require"

# Get database URL
try:
    DATABASE_URL = get_database_url()
except ValueError as e:
    print(f"⚠️  Database configuration error: {e}")
    print("Please set RDS_USERNAME and RDS_PASSWORD environment variables")
    # Fallback to SQLite for development
    DATABASE_URL = "sqlite:///./app.db"

# Create engine with appropriate settings
if DATABASE_URL.startswith("postgresql"):
    # PostgreSQL settings with SSL
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=False,  # Set to True for SQL debugging
        connect_args={
            "sslmode": "require"
        }
    )
else:
    # SQLite settings (fallback)
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# AWS TODO (DynamoDB Usage):
# - For high-scale, flexible metadata (e.g., job progress, per-frame inference), consider DynamoDB tables
# - Create a table (partition key: job_id) to store ephemeral or frequently updated job state
# - Access via boto3 resource: boto3.resource('dynamodb').Table('<table_name>')
# - Use this alongside RDS (normalized relations) to satisfy the two persistence services criterion