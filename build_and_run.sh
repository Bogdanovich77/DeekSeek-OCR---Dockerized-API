#!/bin/bash
set -e

echo "========================================="
echo "DeepSeek-OCR Build and Run Script"
echo "========================================="

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Step 1: Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker found${NC}"

# Check Docker Compose
if ! docker compose version &> /dev/null; then
    echo -e "${RED}✗ Docker Compose plugin not found${NC}"
    echo -e "${YELLOW}Please install Docker Compose v2${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker Compose found${NC}"

# Check NVIDIA GPU
if ! command -v nvidia-smi &> /dev/null; then
    echo -e "${RED}✗ nvidia-smi not found - NVIDIA GPU required${NC}"
    exit 1
fi
echo -e "${GREEN}✓ NVIDIA GPU found${NC}"

# Step 2: Check if setup has been run
echo ""
echo -e "${YELLOW}Checking setup status...${NC}"

SETUP_NEEDED=0

# Check for DeepSeek-OCR source
if [ ! -d "DeepSeek-OCR/DeepSeek-OCR-master/DeepSeek-OCR-vllm" ]; then
    echo -e "${RED}✗ DeepSeek-OCR source code not found${NC}"
    SETUP_NEEDED=1
else
    echo -e "${GREEN}✓ DeepSeek-OCR source code found${NC}"
fi

# Check for model files
if [ ! -f "models/deepseek-ai/DeepSeek-OCR/config.json" ]; then
    echo -e "${RED}✗ Model files not found${NC}"
    SETUP_NEEDED=1
else
    echo -e "${GREEN}✓ Model files found${NC}"
fi

# Run setup if needed
if [ $SETUP_NEEDED -eq 1 ]; then
    echo ""
    echo -e "${YELLOW}=========================================${NC}"
    echo -e "${YELLOW}Setup required before building${NC}"
    echo -e "${YELLOW}=========================================${NC}"
    echo ""

    # Check if setup_local.sh exists
    if [ ! -f "setup_local.sh" ]; then
        echo -e "${RED}✗ setup_local.sh not found${NC}"
        exit 1
    fi

    # Make setup script executable
    chmod +x setup_local.sh

    echo -e "${BLUE}Running setup_local.sh...${NC}"
    ./setup_local.sh || {
        echo -e "${RED}✗ Setup failed${NC}"
        exit 1
    }
    echo ""
fi

# Step 3: Build Docker image
echo -e "${YELLOW}=========================================${NC}"
echo -e "${YELLOW}Building Docker image...${NC}"
echo -e "${YELLOW}=========================================${NC}"
echo ""

docker compose build || {
    echo -e "${RED}✗ Docker build failed${NC}"
    echo ""
    echo -e "${YELLOW}Troubleshooting:${NC}"
    echo -e "  1. Ensure Docker Desktop is running"
    echo -e "  2. Check NVIDIA Container Toolkit: docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu20.04 nvidia-smi"
    echo -e "  3. Free up disk space if needed: docker system prune"
    exit 1
}

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}✓ Build complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""

# Step 4: Ask if user wants to start the service
echo -e "${BLUE}Do you want to start the service now? (y/n)${NC}"
read -r response

if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo ""
    echo -e "${YELLOW}Starting DeepSeek-OCR service...${NC}"
    docker compose up -d

    echo ""
    echo -e "${GREEN}✓ Service started!${NC}"
    echo ""
    echo -e "${BLUE}Checking service health...${NC}"
    echo -e "${YELLOW}(This may take 1-2 minutes for model to load)${NC}"

    # Wait for service to be ready
    sleep 10

    echo ""
    echo -e "${BLUE}Testing health endpoint...${NC}"
    curl -s http://localhost:8000/health | python3 -m json.tool || echo -e "${YELLOW}Service still starting up...${NC}"

    echo ""
    echo -e "${GREEN}=========================================${NC}"
    echo -e "${GREEN}Service is running!${NC}"
    echo -e "${GREEN}=========================================${NC}"
    echo ""
    echo -e "${BLUE}Useful commands:${NC}"
    echo -e "  View logs:      ${YELLOW}docker compose logs -f deepseek-ocr${NC}"
    echo -e "  Health check:   ${YELLOW}curl http://localhost:8000/health${NC}"
    echo -e "  Stop service:   ${YELLOW}docker compose down${NC}"
    echo -e "  Restart:        ${YELLOW}docker compose restart${NC}"
    echo ""
else
    echo ""
    echo -e "${GREEN}Build complete!${NC}"
    echo -e "${BLUE}To start the service later, run:${NC}"
    echo -e "  ${YELLOW}docker compose up -d${NC}"
    echo ""
fi
