# Setup Fix Notes

## Problem Fixed

The original setup had a critical issue where running `docker compose build` and `docker compose up` would fail with:

```
HFValidationError: Repo id must be in the form 'repo_name' or 'namespace/repo_name':
'/app/models/deepseek-ai/DeepSeek-OCR'
```

## Root Cause

The issue was caused by a volume mount conflict:

1. `Dockerfile` ran `setup_deepseek.sh` which downloaded the model **inside the container** during build
2. `docker-compose.yml` had `./models:/app/models` volume mount
3. When container started, the mount **replaced** the container's `/app/models/` with the (empty) host's `./models/` directory
4. Container couldn't find model files and crashed

## Solution

The fix enforces proper setup order:

1. **Download model to HOST first** using `setup_local.sh`
2. **Then build Docker** - `setup_deepseek.sh` no longer downloads model, only clones source code
3. **Then start container** - model is mounted from host via volume

## Changes Made

### 1. Updated `setup_deepseek.sh`
- Removed model download logic (since it would be overridden by volume mount anyway)
- Now only clones DeepSeek-OCR source code
- Added note about volume mount requirement

### 2. Created `build_and_run.sh` (Linux/macOS)
- All-in-one script that enforces correct order
- Checks prerequisites (Docker, GPU, etc.)
- Runs `setup_local.sh` if model/source missing
- Builds Docker image
- Optionally starts service
- Usage: `./build_and_run.sh`

### 3. Updated `build.bat` (Windows)
- Same functionality as `build_and_run.sh` for Windows users
- Checks prerequisites and setup status
- Provides clear error messages if setup needed
- Usage: `build.bat`

### 4. Updated All Scripts to Use `docker compose`
- Changed from deprecated `docker-compose` to `docker compose` (v2 CLI plugin)
- Updated all documentation and scripts

### 5. Updated `CLAUDE.md`
- Added critical "Volume Mount Strategy" section
- Added "HFValidationError" troubleshooting section
- Updated all commands to use `docker compose`
- Clarified setup order requirements

## How to Use Now

### Quick Start (Recommended)

```bash
# Linux/macOS
./build_and_run.sh

# Windows
build.bat
```

These scripts will:
1. Check if model/source are downloaded
2. Run setup if needed
3. Build Docker image
4. Start service (optional)

### Manual Setup (If Needed)

```bash
# Step 1: Download model and clone source (ONE TIME ONLY)
./setup_local.sh

# Step 2: Build Docker image
docker compose build

# Step 3: Start service
docker compose up -d

# Step 4: Check health
curl http://localhost:8000/health
```

## Why This Approach?

**Pros:**
- Model (~15GB) stays on host, not duplicated in Docker image
- Easy to update model without rebuilding container
- Clear separation of concerns: setup vs runtime
- Volume mount allows model sharing between runs

**Cons:**
- Requires extra step before Docker build
- Model must exist on host machine

## What Happens If You Skip Setup?

If you run `docker compose up` without running `setup_local.sh` first:

1. Container starts with empty `/app/models/` directory (from empty host mount)
2. `start_server.py` tries to load model from `/app/models/deepseek-ai/DeepSeek-OCR`
3. Transformers library sees the path and tries to interpret it as a HuggingFace repo ID
4. Validation fails: path format doesn't match `namespace/repo_name` pattern
5. Container exits with `HFValidationError`
6. Docker restart policy keeps retrying, same error repeats

## Testing

To verify the fix works:

```bash
# Clean slate
docker compose down
rm -rf models/ DeepSeek-OCR/

# Run automated setup and build
./build_and_run.sh  # Should complete successfully

# Check logs
docker compose logs deepseek-ocr  # Should show "Model initialization complete!"

# Test API
curl http://localhost:8000/health  # Should return "healthy" status
```

## Files Modified

- `setup_deepseek.sh` - Removed model download, only clones source
- `build_and_run.sh` - NEW: Automated Linux/macOS setup and build script
- `build.bat` - Updated for proper setup enforcement and `docker compose`
- `CLAUDE.md` - Added volume mount explanation and troubleshooting
- `SETUP_FIX_NOTES.md` - NEW: This file

## Files Unchanged

- `setup_local.sh` - Already worked correctly, no changes needed
- `Dockerfile` - No changes needed
- `docker-compose.yml` - No changes needed
- `start_server.py` - No changes needed
- `pdf_to_markdown_processor.py` - No changes needed
