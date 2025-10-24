#!/bin/bash
set -e

echo "========================================="
echo "DeepSeek-OCR Docker Setup Script"
echo "========================================="

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check and clone DeepSeek-OCR source code if needed
echo -e "${YELLOW}Checking DeepSeek-OCR source code...${NC}"
if [ -d "/app/DeepSeek-OCR-vllm" ]; then
    echo -e "${GREEN}✓ DeepSeek-OCR source code already exists${NC}"
else
    echo -e "${YELLOW}⟳ Cloning DeepSeek-OCR from GitHub...${NC}"

    # Clone to temporary location
    git clone https://github.com/deepseek-ai/DeepSeek-OCR.git /tmp/DeepSeek-OCR || {
        echo -e "${RED}✗ Failed to clone DeepSeek-OCR repository${NC}"
        exit 1
    }

    # Copy vLLM implementation to /app
    if [ -d "/tmp/DeepSeek-OCR/DeepSeek-OCR-master/DeepSeek-OCR-vllm" ]; then
        cp -r /tmp/DeepSeek-OCR/DeepSeek-OCR-master/DeepSeek-OCR-vllm /app/
        echo -e "${GREEN}✓ DeepSeek-OCR source code cloned successfully${NC}"
    else
        echo -e "${RED}✗ Unexpected repository structure${NC}"
        ls -la /tmp/DeepSeek-OCR/
        exit 1
    fi

    # Clean up
    rm -rf /tmp/DeepSeek-OCR
fi

# Note: Model files should be downloaded to ./models/ directory on the host
# BEFORE running docker build, using the setup_local.sh script.
# The model directory will be mounted as a volume at runtime.

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}DeepSeek-OCR Source Setup Complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo -e "${YELLOW}Note: Model must be in ./models/ directory on host${NC}"
