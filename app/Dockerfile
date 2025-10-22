# Use Python 3.11 base image
FROM python:3.11-slim-bookworm


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



# Run Worker
CMD ["python", "app/worker.py"]


