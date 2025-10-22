# DeepSeek-OCR: PDF to Markdown Converter

A powerful OCR solution that converts PDF documents to Markdown format using DeepSeek-OCR with FastAPI backend. This project provides both a batch processing script and a REST API for flexible document conversion.

## 🚀 Quick Start

### Option 1: Batch Processing with pdf_to_markdown_processor.py

1. Place your PDF files in the `data/` directory
2. Ensure the DeepSeek-OCR API is running (see Docker setup below)
3. Run the processor:

```bash
python pdf_to_markdown_processor.py
```

### Option 2: REST API with Docker Backend

1. Build and start the Docker container
2. Use the API endpoints to process documents
3. Integrate with your applications

---

## 📋 Prerequisites

### Hardware Requirements
- **NVIDIA GPU** with CUDA 11.8+ support
- **GPU Memory**: Minimum 16GB VRAM (recommended: 40GB+ A100)
- **System RAM**: Minimum 32GB (recommended: 64GB+)
- **Storage**: 50GB+ free space for model and containers

### Software Requirements
- **Python 3.8+** (for local processing)
- **Docker** 20.10+ with GPU support
- **Docker Compose** 2.0+
- **NVIDIA Container Toolkit** installed
- **CUDA 11.8** compatible drivers

---

## 🐳 Docker Backend Setup

### 1. Download Model Weights

Create a directory for model weights and download the DeepSeek-OCR model:

```bash
# Create models directory
mkdir -p models

# Download using Hugging Face CLI
pip install huggingface_hub
huggingface-cli download deepseek-ai/DeepSeek-OCR --local-dir models/deepseek-ai/DeepSeek-OCR

# Or using git
git clone https://huggingface.co/deepseek-ai/DeepSeek-OCR models/deepseek-ai/DeepSeek-OCR
```

### 2. Build and Run the Docker Container

#### Windows Users

```cmd
REM Build the Docker image
build.bat

REM Start the service
docker-compose up -d

REM Check logs
docker-compose logs -f deepseek-ocr
```

#### Linux/macOS Users

```bash
# Build the Docker image
docker-compose build

# Start the service
docker-compose up -d

# Check logs
docker-compose logs -f deepseek-ocr
```

### 3. Verify Installation

```bash
# Health check
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "model_loaded": true,
  "model_path": "/app/models/deepseek-ai/DeepSeek-OCR",
  "cuda_available": true,
  "cuda_device_count": 1
}
```

---

## 📄 Using pdf_to_markdown_processor.py

The `pdf_to_markdown_processor.py` script provides batch processing capabilities for PDF files in the `data/` directory.

### Features
- Automatically scans the `data/` directory for PDF files
- Converts each PDF to Markdown format
- Saves output with the same filename but `.md` extension
- Provides detailed logging and progress tracking
- Handles API connection errors gracefully

### Usage

1. **Prepare PDF Files**
   ```bash
   # Place your PDF files in the data directory
   cp your_document.pdf data/
   cp another_document.pdf data/
   ```

2. **Run the Processor**
   ```bash
   python pdf_to_markdown_processor.py
   ```

3. **Check Results**
   ```bash
   # View generated markdown files
   ls data/*.md
   
   # View processing log
   cat pdf_processor.log
   ```

### Output Format

The processor creates Markdown files with page separators:

```markdown
# Page 1 Content
... OCR results for page 1 ...

<--- Page Split --->

# Page 2 Content
... OCR results for page 2 ...
```

### Configuration

You can modify the processor behavior by editing the script:

```python
# Change data folder
processor = PDFToMarkdownProcessor(data_folder="my_documents")

# Change API URL
processor = PDFToMarkdownProcessor(api_base_url="http://localhost:8000")
```

---

## 🔌 REST API Usage

The FastAPI backend provides several endpoints for document processing.

### API Endpoints

#### Health Check
```bash
GET http://localhost:8000/health
```

#### Process Single Image
```bash
curl -X POST "http://localhost:8000/ocr/image" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@your_image.jpg"
```

#### Process PDF
```bash
curl -X POST "http://localhost:8000/ocr/pdf" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@your_document.pdf"
```

#### Batch Processing
```bash
curl -X POST "http://localhost:8000/ocr/batch" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@image1.jpg" \
  -F "files=@document.pdf" \
  -F "files=@image2.png"
```

### Response Formats

#### Single Image Response
```json
{
  "success": true,
  "result": "# Document Title\n\nThis is the OCR result in markdown format...",
  "page_count": 1
}
```

#### PDF Response
```json
{
  "success": true,
  "results": [
    {
      "success": true,
      "result": "# Page 1 Content\n...",
      "page_count": 1
    },
    {
      "success": true,
      "result": "# Page 2 Content\n...",
      "page_count": 2
    }
  ],
  "total_pages": 2,
  "filename": "document.pdf"
}
```

---

## 💻 Client Integration Examples

### Python Client

```python
import requests

class DeepSeekOCRClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
    
    def process_image(self, image_path):
        with open(image_path, 'rb') as f:
            response = requests.post(
                f"{self.base_url}/ocr/image",
                files={"file": f}
            )
        return response.json()
    
    def process_pdf(self, pdf_path):
        with open(pdf_path, 'rb') as f:
            response = requests.post(
                f"{self.base_url}/ocr/pdf",
                files={"file": f}
            )
        return response.json()

# Usage
client = DeepSeekOCRClient()
result = client.process_pdf("document.pdf")

if result["success"]:
    for page_result in result["results"]:
        print(f"Page {page_result['page_count']}:")
        print(page_result["result"])
        print("---")
```

### JavaScript Client

```javascript
class DeepSeekOCR {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
    }
    
    async processImage(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`${this.baseUrl}/ocr/image`, {
            method: 'POST',
            body: formData
        });
        
        return await response.json();
    }
    
    async processPDF(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`${this.baseUrl}/ocr/pdf`, {
            method: 'POST',
            body: formData
        });
        
        return await response.json();
    }
}

// Usage in browser
const ocr = new DeepSeekOCR();
document.getElementById('fileInput').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    const result = await ocr.processPDF(file);
    
    if (result.success) {
        result.results.forEach(page => {
            console.log(`Page ${page.page_count}:`, page.result);
        });
    }
});
```

---

## ⚙️ Configuration

### Environment Variables

Edit `docker-compose.yml` to adjust these settings:

```yaml
environment:
  - CUDA_VISIBLE_DEVICES=0                    # GPU device to use
  - MODEL_PATH=/app/models/deepseek-ai/DeepSeek-OCR  # Model path
  - MAX_CONCURRENCY=50                         # Max concurrent requests
  - GPU_MEMORY_UTILIZATION=0.85                # GPU memory usage (0.1-1.0)
```

### Performance Tuning

#### For High-Throughput Processing
```yaml
environment:
  - MAX_CONCURRENCY=100
  - GPU_MEMORY_UTILIZATION=0.95
```

#### For Memory-Constrained Systems
```yaml
environment:
  - MAX_CONCURRENCY=10
  - GPU_MEMORY_UTILIZATION=0.7
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. Out of Memory Errors
```bash
# Reduce concurrency and GPU memory usage
# Edit docker-compose.yml:
environment:
  - MAX_CONCURRENCY=10
  - GPU_MEMORY_UTILIZATION=0.7
```

#### 2. Model Loading Issues
```bash
# Check model directory structure
ls -la models/deepseek-ai/DeepSeek-OCR/

# Verify model files are present
docker-compose exec deepseek-ocr ls -la /app/models/deepseek-ai/DeepSeek-OCR/
```

#### 3. CUDA Errors
```bash
# Check GPU availability
nvidia-smi

# Check Docker GPU support
docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu20.04 nvidia-smi
```

#### 4. API Connection Errors
```bash
# Check if the API is running
curl http://localhost:8000/health

# Check container logs
docker-compose logs -f deepseek-ocr

# Restart the service
docker-compose restart deepseek-ocr
```

#### 5. PDF Processing Errors
```bash
# Check if PDF files are valid
file data/your_document.pdf

# Try processing a single PDF manually
curl -X POST "http://localhost:8000/ocr/pdf" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@data/your_document.pdf"
```

### Debug Mode

For debugging, you can run the container with additional tools:

```bash
# Run with shell access
docker-compose run --rm deepseek-ocr bash

# Check model loading
python -c "
import sys
sys.path.insert(0, '/app/DeepSeek-OCR-master/DeepSeek-OCR-vllm')
from config import MODEL_PATH
print(f'Model path: {MODEL_PATH}')
print(f'Model exists: {os.path.exists(MODEL_PATH)}')
"
```

---

## 📊 Performance Tips

1. **Batch Processing**: Process multiple files at once using the `/ocr/batch` endpoint
2. **Optimize DPI**: The default DPI of 144 provides good balance between quality and speed
3. **GPU Utilization**: Adjust `GPU_MEMORY_UTILIZATION` based on your GPU capacity
4. **Concurrency**: Increase `MAX_CONCURRENCY` for better throughput on powerful GPUs
5. **File Size**: For large PDFs, consider splitting them into smaller chunks

---

## 🏗️ Project Structure

```
DeepSeek-OCR/
├── README.md                    # This file
├── pdf_to_markdown_processor.py # Batch processing script
├── start_server.py             # FastAPI server
├── Dockerfile                  # Docker container definition
├── docker-compose.yml          # Docker compose configuration
├── build.bat                   # Windows build script
├── data/                       # Input/output directory for PDFs
├── models/                     # Model weights directory
└── DeepSeek-OCR/               # DeepSeek-OCR source code
```

---

## 📝 License

This project follows the same license as the DeepSeek-OCR project. Please refer to the original project's license file for details.

---

## 🤝 Support

For issues related to:
- **Docker setup**: Check this README first
- **DeepSeek-OCR model**: Refer to the [official repository](https://github.com/deepseek-ai/DeepSeek-OCR)
- **vLLM**: Refer to [vLLM documentation](https://docs.vllm.ai/)

---

## 🔄 Usage Workflow

```mermaid
graph TD
    A[Start] --> B{Choose Method}
    
    B -->|Batch Processing| C[Place PDFs in data/ folder]
    B -->|API Usage| D[Start Docker Container]
    
    C --> E[Run python pdf_to_markdown_processor.py]
    D --> F[Use API endpoints]
    
    E --> G[Check data/ folder for .md files]
    F --> H[Process results from API response]
    
    G --> I[Done]
    H --> I
    
    style A fill:#e1f5fe
    style I fill:#e8f5e8
    style C fill:#fff3e0
    style D fill:#fff3e0
    style E fill:#f3e5f5
    style F fill:#f3e5f5