import runpod
import base64
from io import BytesIO
from PIL import Image
import sys
import os
import json
import requests
import fitz  # PyMuPDF
import subprocess

# Fix transformers version compatibility with PyTorch 2.1.1
print("Checking transformers version compatibility...")
try:
    import transformers
    version = transformers.__version__
    print(f"Current transformers version: {version}")

    # If version is >= 4.37.0, downgrade to 4.36.2 for PyTorch 2.1.1 compatibility
    major, minor = map(int, version.split('.')[:2])
    if major > 4 or (major == 4 and minor >= 37):
        print(f"Incompatible transformers version {version} detected. Downgrading to 4.36.2...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-cache-dir", "transformers==4.36.2"])
        print("Transformers downgraded successfully. Reloading...")
        # Force reload of transformers module
        import importlib
        importlib.reload(transformers)
except Exception as e:
    print(f"Warning during version check: {e}")

# Fix tokenizers version compatibility with DeepSeek-OCR tokenizer.json format
print("Checking tokenizers version compatibility...")
try:
    import tokenizers
    version = tokenizers.__version__
    print(f"Current tokenizers version: {version}")

    # If version is < 0.15.0, upgrade for DeepSeek-OCR tokenizer.json compatibility
    major, minor = map(int, version.split('.')[:2])
    if major == 0 and minor < 15:
        print(f"Incompatible tokenizers version {version} detected. Upgrading to 0.15.2...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-cache-dir", "tokenizers==0.15.2"])
        print("Tokenizers upgraded successfully. Reloading...")
        # Force reload of tokenizers module
        import importlib
        importlib.reload(tokenizers)
except Exception as e:
    print(f"Warning during tokenizers version check: {e}")

# Add DeepSeek-OCR to path
sys.path.insert(0, '/app/DeepSeek-OCR')

from transformers import AutoModel, AutoTokenizer
import torch

# Initialize model at startup
MODEL_PATH = os.environ.get("MODEL_PATH", "/app/models/DeepSeek-OCR")
print(f"Loading model from: {MODEL_PATH}")

tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
model = AutoModel.from_pretrained(
    MODEL_PATH,
    trust_remote_code=True,
    torch_dtype=torch.bfloat16
).cuda().eval()

print("Model loaded successfully!")

# Chunk storage directory (use network volume if available, otherwise /tmp)
CHUNK_STORAGE_DIR = os.environ.get("RUNPOD_VOLUME_PATH", "/tmp") + "/pdf_chunks"
os.makedirs(CHUNK_STORAGE_DIR, exist_ok=True)

def download_from_url(url, timeout=300):
    """Download file from URL"""
    try:
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()
        return response.content
    except Exception as e:
        raise Exception(f"Failed to download from URL: {str(e)}")

def pdf_to_images(pdf_data, dpi=144):
    """Convert PDF bytes to list of PIL Images"""
    images = []
    pdf_document = fitz.open(stream=pdf_data, filetype="pdf")

    for page_num in range(pdf_document.page_count):
        page = pdf_document[page_num]

        # Render page to pixmap
        mat = fitz.Matrix(dpi/72, dpi/72)
        pix = page.get_pixmap(matrix=mat)

        # Convert to PIL Image
        img_data = pix.tobytes("ppm")
        image = Image.open(BytesIO(img_data)).convert("RGB")
        images.append(image)

    pdf_document.close()
    return images

def process_image_with_model(image, prompt, page_num=None):
    """Process a single image with the model"""
    # Save image temporarily
    temp_path = f"/tmp/temp_image_{page_num or 0}.jpg"
    image.save(temp_path)

    # Process with DeepSeek-OCR
    result = model.infer(
        tokenizer,
        prompt=prompt,
        image_file=temp_path,
        output_path="/tmp",
        base_size=1024,
        image_size=640,
        crop_mode=True
    )

    # Clean up temp file
    try:
        os.remove(temp_path)
    except:
        pass

    return result

def handler(event):
    """
    RunPod handler for DeepSeek-OCR

    Supported input methods:

    1. Single Image (base64):
    {
        "input": {
            "image_base64": "base64_encoded_image",
            "prompt": "optional custom prompt"
        }
    }

    2. PDF from base64 (small PDFs only, <7MB):
    {
        "input": {
            "pdf_base64": "base64_encoded_pdf",
            "prompt": "optional custom prompt"
        }
    }

    3. PDF from URL (recommended for large files):
    {
        "input": {
            "pdf_url": "https://example.com/document.pdf",
            "prompt": "optional custom prompt"
        }
    }

    4. Chunked PDF upload:
    {
        "input": {
            "chunk_id": "unique_upload_id",
            "chunk_index": 0,
            "total_chunks": 5,
            "chunk_data": "base64_encoded_chunk",
            "prompt": "optional custom prompt"
        }
    }
    """
    try:
        input_data = event.get("input", {})
        prompt = input_data.get("prompt", "<image>\n<|grounding|>Convert the document to markdown.")

        # Method 1: Handle chunked upload
        if "chunk_data" in input_data:
            return handle_chunked_upload(input_data, prompt)

        # Method 2: Handle PDF from URL
        elif "pdf_url" in input_data:
            pdf_url = input_data["pdf_url"]
            print(f"Downloading PDF from URL: {pdf_url}")
            pdf_data = download_from_url(pdf_url)
            return process_pdf(pdf_data, prompt)

        # Method 3: Handle PDF from base64
        elif "pdf_base64" in input_data:
            print("Processing PDF from base64")
            pdf_data = base64.b64decode(input_data["pdf_base64"])
            return process_pdf(pdf_data, prompt)

        # Method 4: Handle single image (backward compatible)
        elif "image_base64" in input_data:
            print("Processing single image")
            image_bytes = base64.b64decode(input_data["image_base64"])
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            result = process_image_with_model(image, prompt)
            return {
                "success": True,
                "result": result
            }

        else:
            return {
                "error": "No valid input provided. Expected one of: image_base64, pdf_base64, pdf_url, or chunk_data"
            }

    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }

def process_pdf(pdf_data, prompt):
    """Process a complete PDF"""
    print(f"Converting PDF to images (size: {len(pdf_data)} bytes)")
    images = pdf_to_images(pdf_data)
    print(f"Processing {len(images)} pages")

    results = []
    for i, image in enumerate(images):
        print(f"Processing page {i+1}/{len(images)}")
        page_result = process_image_with_model(image, prompt, page_num=i+1)
        results.append({
            "page": i + 1,
            "result": page_result
        })

    return {
        "success": True,
        "total_pages": len(images),
        "results": results
    }

def handle_chunked_upload(input_data, prompt):
    """
    Handle chunked PDF uploads with disk-based storage.
    Works across multiple workers if they share a network volume.
    """
    chunk_id = input_data.get("chunk_id")
    chunk_index = input_data.get("chunk_index")
    total_chunks = input_data.get("total_chunks")
    chunk_data = input_data.get("chunk_data")

    if not all([chunk_id, chunk_index is not None, total_chunks, chunk_data]):
        return {"error": "Missing required chunk parameters"}

    # Create directory for this upload
    upload_dir = os.path.join(CHUNK_STORAGE_DIR, chunk_id)
    os.makedirs(upload_dir, exist_ok=True)

    # Write metadata file on first chunk
    metadata_file = os.path.join(upload_dir, "metadata.json")
    if not os.path.exists(metadata_file):
        with open(metadata_file, 'w') as f:
            json.dump({"total_chunks": total_chunks}, f)

    # Save this chunk to disk
    chunk_file = os.path.join(upload_dir, f"chunk_{chunk_index:04d}.bin")
    chunk_bytes = base64.b64decode(chunk_data)
    with open(chunk_file, 'wb') as f:
        f.write(chunk_bytes)

    print(f"Saved chunk {chunk_index + 1}/{total_chunks} for upload {chunk_id} ({len(chunk_bytes)} bytes)")

    # Check how many chunks we have
    existing_chunks = [f for f in os.listdir(upload_dir) if f.startswith("chunk_")]
    received_chunks = len(existing_chunks)

    print(f"Progress: {received_chunks}/{total_chunks} chunks received")

    # Check if all chunks received
    if received_chunks >= total_chunks:
        print(f"All chunks received for {chunk_id}, assembling PDF...")

        # Assemble PDF from chunks
        pdf_data = b""
        for i in range(total_chunks):
            chunk_file = os.path.join(upload_dir, f"chunk_{i:04d}.bin")
            if not os.path.exists(chunk_file):
                return {"error": f"Missing chunk {i}"}
            with open(chunk_file, 'rb') as f:
                pdf_data += f.read()

        # Clean up chunk files
        try:
            import shutil
            shutil.rmtree(upload_dir)
            print(f"Cleaned up temporary files for {chunk_id}")
        except Exception as e:
            print(f"Warning: Failed to clean up chunks: {e}")

        # Process the complete PDF
        print(f"Assembled PDF: {len(pdf_data)} bytes, processing...")
        return process_pdf(pdf_data, prompt)
    else:
        # Return status - more chunks needed
        return {
            "success": True,
            "status": "chunks_received",
            "received": received_chunks,
            "total": total_chunks,
            "message": f"Received {received_chunks}/{total_chunks} chunks"
        }

runpod.serverless.start({"handler": handler})
