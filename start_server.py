#!/usr/bin/env python3
"""
DeepSeek-OCR vLLM Server
FastAPI wrapper for DeepSeek-OCR with vLLM backend
"""

import os
import sys
import asyncio
import io
import tempfile
from typing import List, Optional
from pathlib import Path

import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form
from typing import Optional
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import torch
import fitz  # PyMuPDF
from PIL import Image
from tqdm import tqdm

# Add current directory to Python path
sys.path.insert(0, '/app/DeepSeek-OCR-vllm')

# Set environment variables for vLLM compatibility
if torch.version.cuda == '11.8':
    os.environ["TRITON_PTXAS_PATH"] = "/usr/local/cuda-11.8/bin/ptxas"
os.environ['VLLM_USE_V1'] = '0'
os.environ["CUDA_VISIBLE_DEVICES"] = '0'

# Import DeepSeek-OCR components
from config import INPUT_PATH, OUTPUT_PATH, PROMPT, CROP_MODE, MAX_CONCURRENCY, NUM_WORKERS
MODEL_PATH = os.environ.get('MODEL_PATH', 'deepseek-ai/DeepSeek-OCR')
from deepseek_ocr import DeepseekOCRForCausalLM
from process.image_process import DeepseekOCRProcessor
from vllm import LLM, SamplingParams
from vllm.model_executor.models.registry import ModelRegistry

# Register the custom model
ModelRegistry.register_model("DeepseekOCRForCausalLM", DeepseekOCRForCausalLM)

# Initialize FastAPI app
app = FastAPI(
    title="DeepSeek-OCR API",
    description="High-performance OCR service using DeepSeek-OCR with vLLM",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for the model
llm = None
sampling_params = None

class OCRResponse(BaseModel):
    success: bool
    result: Optional[str] = None
    error: Optional[str] = None
    page_count: Optional[int] = None

class BatchOCRResponse(BaseModel):
    success: bool
    results: List[OCRResponse]
    total_pages: int
    filename: str

def initialize_model():
    """Initialize the vLLM model"""
    global llm, sampling_params
    
    if llm is None:
        print("Initializing DeepSeek-OCR model...")
        
        # Initialize vLLM engine
        llm = LLM(
            model=MODEL_PATH,
            hf_overrides={"architectures": ["DeepseekOCRForCausalLM"]},
            block_size=256,
            enforce_eager=False,
            trust_remote_code=True,
            max_model_len=8192,
            swap_space=0,
            max_num_seqs=MAX_CONCURRENCY,
            tensor_parallel_size=1,
            gpu_memory_utilization=0.9,
            disable_mm_preprocessor_cache=True
        )
        
        # Set up sampling parameters
        from process.ngram_norepeat import NoRepeatNGramLogitsProcessor
        logits_processors = [NoRepeatNGramLogitsProcessor(ngram_size=20, window_size=50, whitelist_token_ids={128821, 128822})]
        
        sampling_params = SamplingParams(
            temperature=0.0,
            max_tokens=8192,
            logits_processors=logits_processors,
            skip_special_tokens=False,
            include_stop_str_in_output=True,
        )
        
        print("Model initialization complete!")

def pdf_to_images_high_quality(pdf_data: bytes, dpi: int = 144) -> List[Image.Image]:
    """Convert PDF bytes to high-quality PIL Images"""
    images = []
    
    # Save PDF data to temporary file
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
        temp_pdf.write(pdf_data)
        temp_pdf_path = temp_pdf.name
    
    try:
        pdf_document = fitz.open(temp_pdf_path)
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        
        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            
            # Convert to PIL Image
            img_data = pixmap.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            images.append(img)
        
        pdf_document.close()
    finally:
        # Clean up temporary file
        os.unlink(temp_pdf_path)
    
    return images

def process_single_image(image: Image.Image, prompt: str = PROMPT) -> str:
    """Process a single image with DeepSeek-OCR using the specified prompt"""
    print(f"[DEBUG] process_single_image called with prompt: {repr(prompt)}")
    print(f"[DEBUG] Prompt length: {len(prompt)} characters")
    print(f"[DEBUG] Prompt starts with <image>: {prompt.startswith('<image>')}")
    
    # Create request format for vLLM
    request_item = {
        "prompt": prompt,
        "multi_modal_data": {
            "image": DeepseekOCRProcessor().tokenize_with_images(
                prompt=prompt,
                images=[image],
                bos=True,
                eos=True,
                cropping=CROP_MODE
            )
        }
    }
    
    print(f"[DEBUG] Request item prompt: {repr(request_item['prompt'])}")
    print(f"[DEBUG] Request item keys: {list(request_item.keys())}")
    print(f"[DEBUG] Multi-modal data type: {type(request_item['multi_modal_data'])}")
    
    # Generate with vLLM
    print(f"[DEBUG] Sending request to vLLM...")
    outputs = llm.generate([request_item], sampling_params=sampling_params)
    result = outputs[0].outputs[0].text
    
    print(f"[DEBUG] Model output (first 100 chars): {repr(result[:100])}")
    print(f"[DEBUG] Model output length: {len(result)} characters")
    
    # Clean up result
    if '<｜end▁of▁sentence｜>' in result:
        result = result.replace('<｜end▁of▁sentence｜>', '')
        print(f"[DEBUG] Removed end-of-sentence tokens")
    
    return result

@app.on_event("startup")
async def startup_event():
    """Initialize the model on startup"""
    initialize_model()

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "DeepSeek-OCR API is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "model_loaded": llm is not None,
        "model_path": MODEL_PATH,
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0
    }

@app.post("/ocr/image", response_model=OCRResponse)
async def process_image_endpoint(file: UploadFile = File(...), prompt: Optional[str] = Form(None)):
    """Process a single image file with optional custom prompt"""
    try:
        print(f"[DEBUG] Image endpoint called for file: {file.filename}")
        
        # Read image data
        image_data = await file.read()
        print(f"[DEBUG] Read {len(image_data)} bytes of image data")
        
        # Convert to PIL Image
        image = Image.open(io.BytesIO(image_data)).convert('RGB')
        print(f"[DEBUG] Converted to PIL Image, size: {image.size}")
        
        # Debug logging
        print(f"[DEBUG] Received prompt parameter: {repr(prompt)}")
        print(f"[DEBUG] Default PROMPT from config: {repr(PROMPT)}")
        
        # Use provided prompt or default
        use_prompt = prompt if prompt else PROMPT
        print(f"[DEBUG] Image endpoint selected prompt: {repr(use_prompt)}")
        print(f"[DEBUG] Using custom prompt: {prompt is not None}")
        
        # Process with DeepSeek-OCR
        print(f"[DEBUG] Sending image to DeepSeek-OCR...")
        result = process_single_image(image, use_prompt)
        print(f"[DEBUG] OCR complete, output length: {len(result)}")
        
        return OCRResponse(
            success=True,
            result=result,
            page_count=1
        )
        
    except Exception as e:
        print(f"[ERROR] Image endpoint failed: {str(e)}")
        return OCRResponse(
            success=False,
            error=str(e)
        )

@app.post("/ocr/pdf", response_model=BatchOCRResponse)
async def process_pdf_endpoint(file: UploadFile = File(...), prompt: Optional[str] = Form(None)):
    """Process a PDF file with optional custom prompt"""
    try:
        print(f"[DEBUG] PDF endpoint called for file: {file.filename}")
        print(f"[DEBUG] Received prompt parameter: {repr(prompt)}")
        print(f"[DEBUG] Default PROMPT from config: {repr(PROMPT)}")
        
        # Read PDF data
        pdf_data = await file.read()
        print(f"[DEBUG] Read {len(pdf_data)} bytes of PDF data")
        
        # Convert PDF to images
        images = pdf_to_images_high_quality(pdf_data, dpi=144)
        print(f"[DEBUG] Converted PDF to {len(images)} images")
        
        if not images:
            print(f"[DEBUG] No images extracted from PDF")
            return BatchOCRResponse(
                success=False,
                results=[],
                total_pages=0,
                filename=file.filename
            )
        
        # Use provided prompt or default
        use_prompt = prompt if prompt else PROMPT
        print(f"[DEBUG] PDF endpoint selected prompt: {repr(use_prompt)}")
        print(f"[DEBUG] Using custom prompt: {prompt is not None}")
        
        # Process each page
        results = []
        for page_num, image in enumerate(tqdm(images, desc="Processing pages")):
            try:
                print(f"[DEBUG] Processing page {page_num + 1}/{len(images)}")
                result = process_single_image(image, use_prompt)
                results.append(OCRResponse(
                    success=True,
                    result=result,
                    page_count=page_num + 1
                ))
                print(f"[DEBUG] Page {page_num + 1} processed successfully, output length: {len(result)}")
            except Exception as e:
                print(f"[ERROR] Page {page_num + 1} failed: {str(e)}")
                results.append(OCRResponse(
                    success=False,
                    error=f"Page {page_num + 1} error: {str(e)}",
                    page_count=page_num + 1
                ))
        
        print(f"[DEBUG] PDF processing complete: {len(results)} pages processed")
        return BatchOCRResponse(
            success=True,
            results=results,
            total_pages=len(images),
            filename=file.filename
        )
        
    except Exception as e:
        print(f"[ERROR] PDF endpoint failed: {str(e)}")
        return BatchOCRResponse(
            success=False,
            results=[OCRResponse(success=False, error=str(e))],
            total_pages=0,
            filename=file.filename
        )

@app.post("/ocr/batch")
async def process_batch_endpoint(files: List[UploadFile] = File(...), prompt: Optional[str] = Form(None)):
    """Process multiple files (images and PDFs) with optional custom prompt"""
    results = []
    
    for file in files:
        if file.filename.lower().endswith('.pdf'):
            result = await process_pdf_endpoint(file, prompt)
        else:
            result = await process_image_endpoint(file, prompt)
        
        results.append({
            "filename": file.filename,
            "result": result
        })
    
    return {"success": True, "results": results}

if __name__ == "__main__":
    print("Starting DeepSeek-OCR API server...")
    uvicorn.run(
        "start_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1
    )