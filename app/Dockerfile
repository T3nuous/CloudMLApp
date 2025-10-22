# Use Python 3.11 base image
FROM python:3.11-slim-bookworm

# Set environment variables
ENV APP_HOME=/app
ENV DATA_DIR=/data
ENV PYTHONUNBUFFERED=1
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

# Create directories
RUN mkdir -p $APP_HOME $DATA_DIR
WORKDIR $APP_HOME

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git curl build-essential python3-dev \
    libopenblas-dev libblas-dev liblapack-dev \
    libjpeg-dev zlib1g-dev libpng-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install NumPy first (compatible version)
RUN pip install --no-cache-dir numpy==1.26.4

# Install PyTorch and torchvision (compatible with NumPy 1.26.4)
RUN pip install --no-cache-dir torch==2.0.1+cpu torchvision==0.15.2+cpu --index-url https://download.pytorch.org/whl/cpu

# Install other dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ./app ./app

# Ensure data directory exists
RUN python -c "import os; os.makedirs(os.environ.get('DATA_DIR', '/data'), exist_ok=True)"

# Expose FastAPI port
EXPOSE 8080

# Run FastAPI
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

# AWS TODO (Runtime config & IAM):
# - Provide runtime configuration via environment variables and SSM/Secrets; do not bake secrets in the image.
# - Attach IAM role (instance profile or task role) with least-privilege access to S3, RDS, DynamoDB, SSM, Secrets Manager.
# - Ensure security groups allow outgoing access to managed services; restrict inbound to necessary ports.

