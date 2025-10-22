# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DeepSeek-OCR Dockerized API: A containerized OCR solution that converts PDF documents and images to Markdown format using DeepSeek-OCR with vLLM backend. The project provides both a batch processing script (`pdf_to_markdown_processor.py`) and a FastAPI REST API (`start_server.py`).

**Key Technologies:**
- **DeepSeek-OCR**: AI model for OCR (Optical Character Recognition)
- **vLLM v0.8.5**: Inference engine for large vision-language models
- **FastAPI**: REST API framework
- **PyMuPDF (fitz)**: PDF processing library
- **Docker**: Containerization with NVIDIA GPU support

## Architecture

### Two-Mode Operation

1. **Docker API Mode** (Primary): FastAPI server in Docker container with GPU acceleration
   - Model loads once at startup and stays in memory
   - Handles concurrent requests efficiently with vLLM
   - Exposes REST endpoints at `localhost:8000`

2. **Batch Processing Mode**: Python script (`pdf_to_markdown_processor.py`) that:
   - Scans `data/` directory for PDF files
   - Calls the Docker API for each file
   - Saves Markdown output with same filename as PDF but `.md` extension

### Core Components

**`start_server.py`** (FastAPI Server):
- Global model state: `llm` (vLLM engine) and `sampling_params` initialized at startup
- Model path: `/app/models/deepseek-ai/DeepSeek-OCR` (inside container)
- Custom model registration with vLLM: `ModelRegistry.register_model("DeepseekOCRForCausalLM", DeepseekOCRForCausalLM)`
- Image preprocessing: Uses `DeepseekOCRProcessor().tokenize_with_images()` with configurable cropping
- PDF conversion: PyMuPDF renders pages at 144 DPI, then processes as images

**Key API Endpoints:**
- `GET /health`: Health check with CUDA status
- `POST /ocr/image`: Process single image
- `POST /ocr/pdf`: Process PDF (returns page-by-page results)
- `POST /ocr/batch`: Process multiple files

**`pdf_to_markdown_processor.py`** (Batch Processor):
- Multipart/form-data file upload to `/ocr/pdf` endpoint
- Extracts results from `BatchOCRResponse` structure
- Adds `<--- Page Split --->` separators between pages
- Logs to both `pdf_processor.log` and console

### Docker Build Process

**CRITICAL: Volume Mount Strategy**

The project uses **volume mounts** for model files and source code, NOT embedded files in the container. This means:
- Model files must exist in `./models/` on your host machine BEFORE running `docker compose up`
- Source code must exist in `./DeepSeek-OCR/` on your host machine BEFORE building
- These directories are mounted into the container at runtime via `docker-compose.yml`

**Why this approach?**
- Model is ~15GB - too large to embed in Docker image
- Allows easy model updates without rebuilding container
- Source code changes don't require image rebuild (for development)

**Dockerfile workflow:**
1. Base: `vllm/vllm-openai:v0.8.5` (official vLLM image)
2. `setup_deepseek.sh` runs during build:
   - Clones DeepSeek-OCR from GitHub to `/app/DeepSeek-OCR-vllm/`
   - Does NOT download model (expects volume mount)
3. Python dependencies installed with specific versions:
   - `fastapi==0.104.1`, `uvicorn[standard]==0.24.0`
   - `flash-attn==2.7.3` (optional, for performance)
   - `tokenizers==0.13.3` (compatibility requirement)

**Important paths:**
- **Host**: `./models/deepseek-ai/DeepSeek-OCR/` → **Container**: `/app/models/deepseek-ai/DeepSeek-OCR/`
- **Host**: `./DeepSeek-OCR/` (optional) → **Container**: N/A (cloned during build)
- **Container**: `/app/DeepSeek-OCR-vllm/` (source code)
- **Container**: `/app/start_server.py` (API server)

## Development Commands

### Quick Start (Recommended)

**IMPORTANT: You must run setup BEFORE building Docker!**

The model files and source code must be downloaded to your local machine first, as they are mounted as volumes into the container.

```bash
# Linux/macOS - All-in-one script
./build_and_run.sh

# Windows - All-in-one script
build.bat
```

These scripts will:
1. Check prerequisites (Docker, GPU, etc.)
2. Run `setup_local.sh` if needed (downloads model + clones source)
3. Build the Docker image
4. Optionally start the service

### Manual Setup (If needed)

If the automated scripts don't work, follow these steps:

```bash
# Step 1: Run setup script to download model and clone source
./setup_local.sh

# Step 2: Build Docker image (use 'docker compose' not 'docker-compose')
docker compose build

# Step 3: Start API server (detached)
docker compose up -d

# Step 4: Verify it's working
curl http://localhost:8000/health
```

### Docker Operations

```bash
# Start API server (detached)
docker compose up -d

# View logs (follow mode)
docker compose logs -f deepseek-ocr

# Stop server
docker compose down

# Restart server
docker compose restart deepseek-ocr

# Rebuild after code changes
docker compose build
docker compose up -d
```

### Testing API

```bash
# Health check
curl http://localhost:8000/health

# Process single image
curl -X POST "http://localhost:8000/ocr/image" \
  -F "file=@image.jpg"

# Process PDF
curl -X POST "http://localhost:8000/ocr/pdf" \
  -F "file=@document.pdf"
```

### Batch Processing

```bash
# Process all PDFs in data/ directory
python pdf_to_markdown_processor.py

# View processing log
cat pdf_processor.log
```

## Configuration

### Environment Variables (docker-compose.yml)

- `CUDA_VISIBLE_DEVICES`: GPU device ID (default: "0")
- `MODEL_PATH`: Path to model weights (default: "/app/models/deepseek-ai/DeepSeek-OCR")
- `MAX_CONCURRENCY`: Max concurrent requests (default: 5, increase for powerful GPUs)
- `GPU_MEMORY_UTILIZATION`: GPU memory fraction (default: 0.85, range: 0.1-1.0)

### Performance Tuning

**Memory-constrained systems:**
```yaml
MAX_CONCURRENCY=10
GPU_MEMORY_UTILIZATION=0.7
```

**High-throughput systems:**
```yaml
MAX_CONCURRENCY=100
GPU_MEMORY_UTILIZATION=0.95
```

### Model Configuration

Model config is in `/app/DeepSeek-OCR-vllm/config.py` (inside container):
- `MODEL_PATH`: Model directory
- `PROMPT`: OCR prompt template
- `CROP_MODE`: Image preprocessing mode
- `NUM_WORKERS`: Worker processes

## Key Implementation Details

### vLLM Initialization (start_server.py:84-96)

```python
llm = LLM(
    model=MODEL_PATH,
    hf_overrides={"architectures": ["DeepseekOCRForCausalLM"]},
    block_size=256,
    enforce_eager=False,
    trust_remote_code=True,
    max_model_len=8192,
    tensor_parallel_size=1,
    gpu_memory_utilization=0.9,
    disable_mm_preprocessor_cache=True
)
```

**Critical parameters:**
- `hf_overrides`: Required to use custom model architecture
- `max_model_len=8192`: Context length for OCR output
- `disable_mm_preprocessor_cache=True`: Necessary for multimodal processing

### PDF to Image Conversion (start_server.py:112-140)

Uses PyMuPDF with 144 DPI default:
```python
zoom = dpi / 72.0
matrix = fitz.Matrix(zoom, zoom)
pixmap = page.get_pixmap(matrix=matrix, alpha=False)
```

Higher DPI = better quality but slower processing.

### Result Cleanup

Model output includes special tokens that are stripped:
```python
if '<｜end▁of▁sentence｜>' in result:
    result = result.replace('<｜end▁of▁sentence｜>', '')
```

## Hardware Requirements

**Minimum:**
- NVIDIA GPU with 16GB VRAM
- CUDA 11.8+ compatible drivers
- 32GB system RAM
- 50GB storage for model + containers

**Recommended:**
- NVIDIA A100 (40GB+ VRAM)
- 64GB+ system RAM
- NVMe storage for model files

## Troubleshooting

### HFValidationError: Repo id must be in the form 'repo_name' or 'namespace/repo_name'

**Symptom:** Container exits with error about `/app/models/deepseek-ai/DeepSeek-OCR` not being a valid repo ID.

**Root Cause:** The model files don't exist in your local `./models/` directory. The container tries to load from the mounted volume but finds it empty.

**Solution:**
```bash
# STOP the container first
docker compose down

# Run setup to download model and source code
./setup_local.sh  # Linux/macOS
# OR manually:
pip install huggingface-hub
huggingface-cli download deepseek-ai/DeepSeek-OCR --local-dir ./models/deepseek-ai/DeepSeek-OCR

# Verify files exist locally
ls -la ./models/deepseek-ai/DeepSeek-OCR/

# Rebuild and start
docker compose build
docker compose up -d
```

**Why this happens:**
The `docker-compose.yml` has `./models:/app/models` volume mount. If `./models/` is empty on your host, it **overrides** the container's `/app/models/` directory, making it empty too.

### Model Loading Issues

Check if model files exist on **host machine**:
```bash
# Should show config.json, tokenizer_config.json, and model weights
ls -la ./models/deepseek-ai/DeepSeek-OCR/
```

Check model directory **inside container**:
```bash
docker compose exec deepseek-ocr ls -la /app/models/deepseek-ai/DeepSeek-OCR/
```

If files exist on host but not in container, check volume mount in `docker-compose.yml`.

### GPU/CUDA Issues

Verify GPU access inside container:
```bash
docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu20.04 nvidia-smi
```

If this fails, NVIDIA Container Toolkit is not properly installed.

### API Connection Errors

The batch processor tests connection at startup. If it fails:
1. Check if container is running: `docker compose ps`
2. Check container logs: `docker compose logs deepseek-ocr`
3. Verify port mapping: `docker compose port deepseek-ocr 8000`

### Container Keeps Restarting

Check logs to see error:
```bash
docker compose logs deepseek-ocr
```

Common causes:
- Model files missing (see HFValidationError above)
- CUDA/GPU not available
- Out of memory
- Port 8000 already in use

### Out of Memory Errors

1. Reduce `MAX_CONCURRENCY` in docker-compose.yml
2. Lower `GPU_MEMORY_UTILIZATION` to 0.7 or less
3. Process smaller batches
4. Check GPU usage: `nvidia-smi`

## Code Patterns

### Adding New Endpoints

Follow FastAPI patterns in `start_server.py`:
1. Define response model with Pydantic
2. Use `UploadFile = File(...)` for file uploads
3. Process with `process_single_image()` helper
4. Return structured response with success/error fields

### Modifying Batch Processor

Key methods in `PDFToMarkdownProcessor`:
- `_call_ocr_api()`: Handles API communication
- `convert_pdf_to_markdown()`: Single file conversion
- `scan_and_process_all_pdfs()`: Batch processing loop

### Custom Image Preprocessing

Modify `DeepseekOCRProcessor().tokenize_with_images()` parameters:
- `cropping=CROP_MODE`: Image crop strategy
- `bos=True, eos=True`: Add begin/end of sequence tokens

## Important Notes

### Critical Setup Order
1. **FIRST**: Run `./setup_local.sh` (or `build_and_run.sh`) to download model and clone source
2. **SECOND**: Run `docker compose build` to build the image
3. **THIRD**: Run `docker compose up -d` to start the service

**DO NOT** skip step 1! The model must exist on your host machine in `./models/` before starting the container.

### Volume Mount Behavior
- `./models:/app/models` - Model files loaded from your local disk into container
- Changes to model on host are immediately visible in running container (no rebuild needed)
- If `./models/` is empty on host, it will be empty in container (causing startup failure)

### Runtime Characteristics
- **Model stays loaded**: The vLLM engine loads once at startup and persists in memory (1-2 min startup time)
- **Single worker**: FastAPI runs with `workers=1` because vLLM handles concurrency internally via `MAX_CONCURRENCY`
- **Special tokens**: Model outputs include `<｜end▁of▁sentence｜>` that must be stripped
- **Page splits**: Batch processor adds `<--- Page Split --->` markers between pages
- **Temporary files**: PDF processing creates temp files that are automatically cleaned up
- **PYTHONPATH**: DeepSeek-OCR source must be in path (`/app/DeepSeek-OCR-vllm`)

### Docker Compose vs docker-compose
- Use `docker compose` (Docker CLI plugin, v2)
- NOT `docker-compose` (standalone tool, deprecated and removed)
- All scripts in this project use the new `docker compose` format
