# DeepSeek-OCR vLLM Docker Image
# Based on official vLLM OpenAI image for better compatibility

FROM vllm/vllm-openai:v0.8.5

# Switch to root user to install packages
USER root

# Set working directory
WORKDIR /app

# Install git and huggingface-cli
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir huggingface-hub

# Copy setup script
COPY setup_deepseek.sh /app/setup_deepseek.sh
RUN chmod +x /app/setup_deepseek.sh

# Run setup to clone repo and download model
# This will automatically clone DeepSeek-OCR if not found
RUN /app/setup_deepseek.sh

# Copy the startup script
COPY start_server.py .

# Install Python dependencies
RUN pip install --no-cache-dir \
    PyMuPDF \
    img2pdf \
    einops \
    easydict \
    addict \
    Pillow \
    numpy \
    tqdm \
    requests \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    python-multipart==0.0.6

# Install flash-attn for optimal performance
RUN pip install --no-cache-dir flash-attn==2.7.3 --no-build-isolation || echo "flash-attn may already be installed"

# Install compatible tokenizers version
RUN pip install --no-cache-dir tokenizers==0.13.3 || echo "Using existing tokenizers version"

# Add the DeepSeek-OCR directory to PYTHONPATH
ENV PYTHONPATH="/app/DeepSeek-OCR-vllm:${PYTHONPATH}"

# Create directories for outputs
RUN mkdir -p /app/outputs

# Make the startup script executable
RUN chmod +x /app/start_server.py

# Expose the API port
EXPOSE 8000

# Set the default command to use our custom server
# Override the entrypoint to run our script directly
# Use the full path to python to avoid PATH issues
ENTRYPOINT ["/usr/bin/python3", "/app/start_server.py"]
