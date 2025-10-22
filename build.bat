@echo off
REM DeepSeek-OCR Build and Run Script for Windows
REM This script enforces proper setup order before building

echo =========================================
echo DeepSeek-OCR Build and Run Script
echo =========================================
echo.

REM Step 1: Check prerequisites
echo Checking prerequisites...

REM Check Docker
docker --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Docker is not installed
    pause
    exit /b 1
)
echo ✓ Docker found

REM Check Docker Compose
docker compose version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Docker Compose plugin not found
    echo Please install Docker Compose v2
    pause
    exit /b 1
)
echo ✓ Docker Compose found

REM Check NVIDIA GPU
nvidia-smi >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ nvidia-smi not found - NVIDIA GPU required
    pause
    exit /b 1
)
echo ✓ NVIDIA GPU found
echo.

REM Step 2: Check if setup has been run
echo Checking setup status...
set SETUP_NEEDED=0

REM Check for DeepSeek-OCR source
if not exist "DeepSeek-OCR\DeepSeek-OCR-master\DeepSeek-OCR-vllm" (
    echo ❌ DeepSeek-OCR source code not found
    set SETUP_NEEDED=1
) else (
    echo ✓ DeepSeek-OCR source code found
)

REM Check for model files
if not exist "models\deepseek-ai\DeepSeek-OCR\config.json" (
    echo ❌ Model files not found
    set SETUP_NEEDED=1
) else (
    echo ✓ Model files found
)

if %SETUP_NEEDED% EQU 1 (
    echo.
    echo =========================================
    echo Setup required before building
    echo =========================================
    echo.
    echo Please run setup_local.sh first or manually:
    echo   1. Install huggingface-cli: pip install huggingface-hub
    echo   2. Clone DeepSeek-OCR: git clone https://github.com/deepseek-ai/DeepSeek-OCR.git
    echo   3. Download model: huggingface-cli download deepseek-ai/DeepSeek-OCR --local-dir models\deepseek-ai\DeepSeek-OCR
    echo.
    pause
    exit /b 1
)

REM Step 3: Build Docker image
echo.
echo =========================================
echo Building Docker image...
echo =========================================
echo.

docker compose build

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ Docker build failed
    echo.
    echo Troubleshooting:
    echo   1. Ensure Docker Desktop is running
    echo   2. Check NVIDIA Container Toolkit: docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu20.04 nvidia-smi
    echo   3. Free up disk space if needed: docker system prune
    echo.
    pause
    exit /b 1
)

echo.
echo =========================================
echo ✓ Build complete!
echo =========================================
echo.

REM Step 4: Ask if user wants to start the service
set /p START_SERVICE="Do you want to start the service now? (y/n): "

if /i "%START_SERVICE%"=="y" (
    echo.
    echo Starting DeepSeek-OCR service...
    docker compose up -d

    echo.
    echo ✓ Service started!
    echo.
    echo Checking service health...
    echo ^(This may take 1-2 minutes for model to load^)
    timeout /t 10 >nul

    echo.
    echo Testing health endpoint...
    curl -s http://localhost:8000/health

    echo.
    echo =========================================
    echo Service is running!
    echo =========================================
    echo.
    echo Useful commands:
    echo   View logs:      docker compose logs -f deepseek-ocr
    echo   Health check:   curl http://localhost:8000/health
    echo   Stop service:   docker compose down
    echo   Restart:        docker compose restart
    echo.
) else (
    echo.
    echo Build complete!
    echo To start the service later, run:
    echo   docker compose up -d
    echo.
)

pause