#!/bin/bash
set -e

echo "========================================="
echo "DeepSeek-OCR Setup Script"
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

# Check and download model
echo -e "${YELLOW}Checking DeepSeek-OCR model...${NC}"
MODEL_PATH="/app/models/deepseek-ai/DeepSeek-OCR"

if [ -d "$MODEL_PATH" ] && [ -f "$MODEL_PATH/config.json" ]; then
    echo -e "${GREEN}✓ DeepSeek-OCR model already exists at $MODEL_PATH${NC}"
else
    echo -e "${YELLOW}⟳ Downloading DeepSeek-OCR model from Hugging Face...${NC}"
    echo -e "${YELLOW}   This may take a while (model size: ~15GB)...${NC}"

    # Create models directory
    mkdir -p /app/models/deepseek-ai

    # Download using huggingface-cli
    huggingface-cli download \
        deepseek-ai/DeepSeek-OCR \
        --local-dir "$MODEL_PATH" \
        --local-dir-use-symlinks False || {
        echo -e "${RED}✗ Failed to download model from Hugging Face${NC}"
        echo -e "${YELLOW}You may need to set HF_TOKEN environment variable for private models${NC}"
        exit 1
    }

    echo -e "${GREEN}✓ DeepSeek-OCR model downloaded successfully${NC}"
fi

# Verify model files
echo -e "${YELLOW}Verifying model files...${NC}"
REQUIRED_FILES=("config.json" "tokenizer_config.json")
ALL_FOUND=true

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$MODEL_PATH/$file" ]; then
        echo -e "${GREEN}✓ Found $file${NC}"
    else
        echo -e "${RED}✗ Missing $file${NC}"
        ALL_FOUND=false
    fi
done

if [ "$ALL_FOUND" = true ]; then
    echo -e "${GREEN}✓ All required model files verified${NC}"
else
    echo -e "${RED}✗ Model verification failed${NC}"
    exit 1
fi

# Update config.py if it exists
if [ -f "/app/DeepSeek-OCR-vllm/config.py" ]; then
    echo -e "${YELLOW}Updating model path in config.py...${NC}"
    sed -i "s|MODEL_PATH = .*|MODEL_PATH = '$MODEL_PATH'|g" /app/DeepSeek-OCR-vllm/config.py
    echo -e "${GREEN}✓ Config updated${NC}"
fi

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}DeepSeek-OCR Setup Complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
