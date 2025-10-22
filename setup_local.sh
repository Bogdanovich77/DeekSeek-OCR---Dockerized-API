#!/bin/bash
set -e

echo "========================================="
echo "DeepSeek-OCR Local Setup Script"
echo "========================================="
echo ""
echo "This script will help you set up DeepSeek-OCR"
echo "and download the model before building Docker."
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check Python and pip
echo -e "${YELLOW}Checking dependencies...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python3 is required but not installed${NC}"
    exit 1
fi

if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}✗ pip3 is required but not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python and pip found${NC}"

# Install huggingface-cli if not present
if ! command -v huggingface-cli &> /dev/null; then
    echo -e "${YELLOW}⟳ Installing huggingface-cli...${NC}"
    pip3 install huggingface-hub
fi

# Create models directory
echo -e "${YELLOW}Creating directory structure...${NC}"
mkdir -p models/deepseek-ai

# Check for DeepSeek-OCR source code
echo -e "${YELLOW}Checking DeepSeek-OCR source code...${NC}"
if [ -d "DeepSeek-OCR/DeepSeek-OCR-master/DeepSeek-OCR-vllm" ]; then
    echo -e "${GREEN}✓ DeepSeek-OCR source code found${NC}"
elif [ -d "DeepSeek-OCR" ]; then
    echo -e "${RED}✗ DeepSeek-OCR directory exists but has unexpected structure${NC}"
    echo -e "${YELLOW}Expected: DeepSeek-OCR/DeepSeek-OCR-master/DeepSeek-OCR-vllm/${NC}"
    echo -e "${YELLOW}Found:${NC}"
    ls -la DeepSeek-OCR/ | head -10
    echo ""
    echo -e "${YELLOW}Removing and re-cloning...${NC}"
    rm -rf DeepSeek-OCR
    git clone https://github.com/deepseek-ai/DeepSeek-OCR.git DeepSeek-OCR || {
        echo -e "${RED}✗ Failed to clone repository${NC}"
        exit 1
    }
    echo -e "${GREEN}✓ Repository cloned successfully${NC}"
else
    echo -e "${YELLOW}⟳ DeepSeek-OCR not found, cloning from GitHub...${NC}"
    git clone https://github.com/deepseek-ai/DeepSeek-OCR.git DeepSeek-OCR || {
        echo -e "${RED}✗ Failed to clone repository${NC}"
        exit 1
    }
    echo -e "${GREEN}✓ Repository cloned successfully${NC}"
fi

# Check and download model
echo -e "${YELLOW}Checking DeepSeek-OCR model...${NC}"
MODEL_PATH="./models/deepseek-ai/DeepSeek-OCR"

if [ -d "$MODEL_PATH" ] && [ -f "$MODEL_PATH/config.json" ]; then
    echo -e "${GREEN}✓ DeepSeek-OCR model already exists${NC}"
    echo -e "${BLUE}ℹ Model location: $MODEL_PATH${NC}"
else
    echo -e "${YELLOW}⟳ Downloading DeepSeek-OCR model from Hugging Face...${NC}"
    echo -e "${YELLOW}   This may take a while (model size: ~15GB)...${NC}"
    echo -e "${BLUE}   You can cancel and restart this later - it will resume${NC}"
    echo ""

    # Download using huggingface-cli
    huggingface-cli download \
        deepseek-ai/DeepSeek-OCR \
        --local-dir "$MODEL_PATH" \
        --local-dir-use-symlinks False \
        --resume-download || {
        echo -e "${RED}✗ Failed to download model${NC}"
        echo -e "${YELLOW}If this is a private model, set HF_TOKEN:${NC}"
        echo -e "${BLUE}export HF_TOKEN=your_token_here${NC}"
        exit 1
    }

    echo -e "${GREEN}✓ Model downloaded successfully${NC}"
fi

# Verify setup
echo ""
echo -e "${YELLOW}Verifying setup...${NC}"
ISSUES=0

if [ ! -d "DeepSeek-OCR/DeepSeek-OCR-master" ]; then
    echo -e "${RED}✗ DeepSeek-OCR source not found${NC}"
    ((ISSUES++))
else
    echo -e "${GREEN}✓ DeepSeek-OCR source verified${NC}"
fi

if [ ! -f "models/deepseek-ai/DeepSeek-OCR/config.json" ]; then
    echo -e "${RED}✗ Model files incomplete${NC}"
    ((ISSUES++))
else
    echo -e "${GREEN}✓ Model files verified${NC}"
fi

if [ ! -f "DeepSeek-OCR/requirements.txt" ]; then
    echo -e "${YELLOW}⚠ requirements.txt not found (will be created)${NC}"
fi

echo ""
if [ $ISSUES -eq 0 ]; then
    echo -e "${GREEN}=========================================${NC}"
    echo -e "${GREEN}✓ Setup Complete!${NC}"
    echo -e "${GREEN}=========================================${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo -e "  1. Build the Docker image:"
    echo -e "     ${YELLOW}docker-compose build${NC}"
    echo -e "  2. Start the service:"
    echo -e "     ${YELLOW}docker-compose up${NC}"
    echo ""
else
    echo -e "${RED}=========================================${NC}"
    echo -e "${RED}✗ Setup completed with $ISSUES issue(s)${NC}"
    echo -e "${RED}=========================================${NC}"
    exit 1
fi
