# DeepSeek-OCR Quick Start Guide

This guide will help you set up and run the DeepSeek-OCR API with Docker.

## Prerequisites

- Docker and Docker Compose installed
- At least 20GB of free disk space (for model)
- NVIDIA GPU with CUDA support (for inference)
- Git (for cloning repository)

## Required First Step

**Clone the DeepSeek-OCR repository:**

```bash
git clone https://github.com/deepseek-ai/DeepSeek-OCR.git DeepSeek-OCR
```

This is **required** before any Docker build. The Dockerfile copies files from this local clone.

## Two Setup Options

### Option 1: Automatic Model Download (During Docker Build)

Docker will automatically download the model during build:

```bash
# Clone repo first (if not done above)
git clone https://github.com/deepseek-ai/DeepSeek-OCR.git DeepSeek-OCR

# Build and run
docker-compose build
docker-compose up
```

**Note:** This will download ~15GB during the Docker build.

### Option 2: Pre-download Model (Recommended for Faster Rebuilds)

Download the model locally first, then build Docker:

```bash
# Clone repo first (if not done above)
git clone https://github.com/deepseek-ai/DeepSeek-OCR.git DeepSeek-OCR

# Download model locally
./setup_local.sh

# Build and run Docker
docker-compose build
docker-compose up
```

**Benefits:**
- Faster Docker rebuilds (model is cached locally)
- Can resume interrupted downloads
- Reusable across multiple builds

## Verifying the Setup

Once running, test the API:

```bash
# Health check
curl http://localhost:8000/health

# Test OCR with an image
curl -X POST http://localhost:8000/ocr/image \
  -F "file=@/path/to/your/image.jpg"
```

## Troubleshooting

### Missing DeepSeek-OCR Source

If Docker build fails with "DeepSeek-OCR source code not found":

```bash
# Clone the repository
git clone https://github.com/deepseek-ai/DeepSeek-OCR.git DeepSeek-OCR

# Verify the structure
ls DeepSeek-OCR/DeepSeek-OCR-master/DeepSeek-OCR-vllm/
```

### Model Download Fails

Use the pre-download option (Option 2) if automatic download fails during Docker build.
