"""
Database configuration for shared PostgreSQL database
This module provides utilities for connecting to the shared cohort database.
"""

import os
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseConfig:
    """Configuration class for shared PostgreSQL database connection"""
    
    def __init__(self):
        self.host = "database-1-instance-1.ce2haupt2cta.ap-southeast-2.rds.amazonaws.com"
        self.port = 5432
        self.database = "cohort_2025"
        self.username = os.environ.get('RDS_USERNAME')
        self.password = os.environ.get('RDS_PASSWORD')
        self.sslmode = "require"
    
    def get_connection_string(self) -> str:
        """Get PostgreSQL connection string"""
        if not self.username or not self.password:
            raise ValueError(
                "RDS_USERNAME and RDS_PASSWORD environment variables must be set. "
                "Please check your Canvas messages for your unique credentials."
            )
        
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}?sslmode={self.sslmode}"
    
    def get_sqlalchemy_url(self) -> str:
        """Get SQLAlchemy connection URL"""
        return f"postgresql+psycopg2://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}?sslmode={self.sslmode}"
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.username,
                password=self.password,
                sslmode=self.sslmode
            )
            conn.close()
            logger.info("✅ Database connection successful")
            return True
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            return False
    
    def get_connection(self):
        """Get a database connection"""
        if not self.username or not self.password:
            raise ValueError("Database credentials not provided")
        
        return psycopg2.connect(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.username,
            password=self.password,
            sslmode=self.sslmode,
            cursor_factory=RealDictCursor
        )

# Global instance
db_config = DatabaseConfig()

def get_db_connection():
    """Get a database connection for use in the application"""
    return db_config.get_connection()

def test_database_connection():
    """Test the database connection and return status"""
    return db_config.test_connection()

def get_database_info():
    """Get database connection information (without credentials)"""
    return {
        "host": db_config.host,
        "port": db_config.port,
        "database": db_config.database,
        "ssl_mode": db_config.sslmode,
        "credentials_provided": bool(db_config.username and db_config.password)
    }
