# Fix Docker Build Setup and Volume Mount Issue

## Problem Fixed

The current Docker setup fails with `HFValidationError` when running `docker compose build && docker compose up` because of a volume mount conflict:

```
HFValidationError: Repo id must be in the form 'repo_name' or 'namespace/repo_name':
'/app/models/deepseek-ai/DeepSeek-OCR'
```

### Root Cause

1. `Dockerfile` runs `setup_deepseek.sh` which downloads the model **inside the container** during build
2. `docker-compose.yml` has `./models:/app/models` volume mount
3. When container starts, the mount **overwrites** the container's `/app/models/` with the (empty) host's `./models/` directory
4. Container can't find model files and crashes with `HFValidationError`

## Solution

This PR fixes the issue by enforcing proper setup order:

1. **Download model to HOST first** using `setup_local.sh`
2. **Then build Docker** - `setup_deepseek.sh` now only clones source code
3. **Then start container** - model is mounted from host via volume

## Key Changes

### New Files Added

1. **`setup_local.sh`** - Pre-build setup script
   - Downloads DeepSeek-OCR model (~15GB) to `./models/`
   - Clones DeepSeek-OCR source code
   - Validates setup completion
   - Must be run BEFORE `docker compose build`

2. **`build_and_run.sh`** (Linux/macOS) - All-in-one automated script
   - Checks prerequisites (Docker, GPU, nvidia-smi)
   - Runs `setup_local.sh` if needed
   - Builds Docker image
   - Optionally starts the service
   - Provides clear error messages

3. **`CLAUDE.md`** - Comprehensive codebase documentation
   - Architecture overview and key implementation details
   - Volume mount strategy explanation
   - Development commands and workflows
   - Troubleshooting guide for common issues
   - Critical setup order requirements

4. **`SETUP_FIX_NOTES.md`** - Detailed explanation of the fix
   - Root cause analysis
   - Solution approach
   - Testing procedures
   - Before/after comparison

### Modified Files

1. **`setup_deepseek.sh`**
   - **Removed** model download logic (would be overridden by volume mount)
   - Now only clones DeepSeek-OCR source code from GitHub
   - Added note about volume mount requirement

2. **`build.bat`** (Windows)
   - Added prerequisite checks (Docker, Docker Compose, GPU)
   - Added setup status verification
   - Enforces setup order before building
   - Prevents build if model/source missing
   - Interactive service startup option
   - Updated to use `docker compose` (v2) instead of deprecated `docker-compose`
   - Integrated upstream's OCR functionality notes

3. **All script references updated**
   - Changed from deprecated `docker-compose` to `docker compose` (Docker CLI plugin v2)
   - Updated all documentation and scripts accordingly

## Breaking Changes

### REQUIRED: Run Setup Before Building

Users **must** now run `setup_local.sh` (or `build_and_run.sh`) before building Docker:

```bash
# OLD (broken) workflow:
docker compose build
docker compose up -d

# NEW (correct) workflow:
./setup_local.sh          # Download model first
docker compose build      # Then build
docker compose up -d      # Then start

# OR use automated script:
./build_and_run.sh        # Handles everything
```

### Why This Approach?

**Pros:**
- Model (~15GB) stays on host, not duplicated in Docker image layers
- Easy to update model without rebuilding container
- Clear separation between setup (one-time) and runtime
- Volume mount allows model sharing between container runs
- Faster subsequent builds (no model download)

**Cons:**
- Requires extra step before Docker build (mitigated by automated scripts)
- Model must exist on host machine

## Testing Performed

Tested the complete workflow from clean state:

```bash
# Clean slate
docker compose down
rm -rf models/ DeepSeek-OCR/

# Run automated setup
./build_and_run.sh

# Verify service started
curl http://localhost:8000/health
# Returns: {"status": "healthy", "model_loaded": true, ...}

# Test API endpoint
curl -X POST "http://localhost:8000/ocr/pdf" -F "file=@test.pdf"
# Successfully processes PDF
```

## Compatibility

- ✅ Compatible with all upstream changes (custom prompts, enhanced processors)
- ✅ Preserves all existing functionality
- ✅ Works on Linux, macOS, and Windows
- ✅ No changes to API endpoints or response formats
- ✅ Existing `docker-compose.yml` unchanged
- ✅ Python scripts continue to work as before

## Documentation Updates

- Added comprehensive setup instructions in `CLAUDE.md`
- Added troubleshooting section for `HFValidationError`
- Updated all command examples to use `docker compose` (v2)
- Clarified volume mount behavior
- Added critical setup order documentation

## Merge Notes

This PR includes a merge of upstream changes from `main` branch:
- Custom prompt support with YAML configuration
- Enhanced PDF processors with image extraction
- OCR-specific processing scripts
- Updated GPU memory requirements (12GB minimum)
- Additional custom configuration files

All conflicts have been resolved while preserving both the fixes from this branch and the new features from upstream.

## Checklist

- [x] Tested on clean environment
- [x] Verified model loading works
- [x] API endpoints functional
- [x] Batch processor works
- [x] Documentation updated
- [x] Scripts use `docker compose` (not `docker-compose`)
- [x] Conflicts resolved
- [x] No breaking changes to API

## Related Issues

Fixes the Docker build failure reported by users trying to follow README setup instructions.

---

**Note**: This is a critical fix for users unable to run the Docker container. Without this fix, following the README instructions results in immediate container failure.
