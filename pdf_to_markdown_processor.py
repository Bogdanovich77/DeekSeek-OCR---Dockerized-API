#!/usr/bin/env python3
"""
PDF to Markdown Processor

This application scans the /data folder for PDF files and converts them to Markdown format
using the DeepSeek OCR API at localhost:8000. Each PDF file is converted to a Markdown 
file with the same name in the same /data folder.
"""

import os
import sys
import glob
import logging
import base64
import json
import requests
from pathlib import Path
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pdf_processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    RESET = '\033[0m'


class PDFToMarkdownProcessor:
    """Processor for converting PDF files to Markdown using DeepSeek OCR API"""
    
    def __init__(self, data_folder: str = "data", api_base_url: str = "http://localhost:8000", max_workers: Optional[int] = None):
        """
        Initialize the PDF processor
        
        Args:
            data_folder: Path to the folder containing PDF files
            api_base_url: Base URL of the DeepSeek OCR API
            max_workers: Maximum number of concurrent requests (default: from MAX_WORKERS env or 5)
        """
        self.data_folder = Path(data_folder)
        self.data_folder.mkdir(exist_ok=True)
        self.api_base_url = api_base_url
        # Get max_workers from environment variable if not provided
        if max_workers is None:
            max_workers = int(os.getenv('MAX_WORKERS', '5'))
        self.max_workers = max_workers
        
        # Test API connection
        if not self._test_api_connection():
            raise ConnectionError(f"Cannot connect to API at {api_base_url}")
    
    def _test_api_connection(self) -> bool:
        """Test if the API is accessible"""
        try:
            response = requests.get(f"{self.api_base_url}/docs", timeout=5)
            if response.status_code == 200:
                logger.info("API connection successful")
                return True
            else:
                logger.error(f"API returned status code: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"API connection failed: {str(e)}")
            return False
    
    def _get_api_endpoints(self) -> Dict[str, str]:
        """Get available API endpoints"""
        try:
            response = requests.get(f"{self.api_base_url}/openapi.json", timeout=5)
            if response.status_code == 200:
                openapi_spec = response.json()
                endpoints = {}
                for path, methods in openapi_spec.get("paths", {}).items():
                    for method, details in methods.items():
                        if method.upper() in ["POST", "GET"]:
                            operation_id = details.get("operationId", "")
                            if "pdf" in operation_id.lower() or "ocr" in operation_id.lower():
                                endpoints[operation_id] = f"{method.upper()} {path}"
                return endpoints
            else:
                logger.error(f"Failed to get API spec: {response.status_code}")
                return {}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting API spec: {str(e)}")
            return {}
    
    def _encode_pdf_to_base64(self, pdf_path: str) -> str:
        """
        Encode a PDF file to base64
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Base64 encoded string of the PDF
        """
        with open(pdf_path, "rb") as pdf_file:
            return base64.b64encode(pdf_file.read()).decode('utf-8')
    
    def _call_ocr_api(self, pdf_path: str) -> Optional[str]:
        """
        Call the OCR API to process a PDF file
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Markdown content or None if processing failed
        """
        try:
            # Use the correct endpoint based on the API documentation
            endpoint = "/ocr/pdf"
            url = f"{self.api_base_url}{endpoint}"
            
            logger.info(f"Processing PDF with API endpoint: {url}")
            
            # Prepare the file for multipart/form-data upload
            with open(pdf_path, 'rb') as pdf_file:
                files = {'file': (os.path.basename(pdf_path), pdf_file, 'application/pdf')}
                
                # Use hardcoded markdown-specific prompt for this request
                markdown_prompt = '<image>\n<|grounding|>Convert the document to markdown.'
                data = {'prompt': markdown_prompt}
                
                response = requests.post(url, files=files, data=data, timeout=300)
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Successfully processed PDF using endpoint: {endpoint}")
                    
                    # Extract markdown content from BatchOCRResponse
                    if isinstance(result, dict):
                        # Check if this is a batch response with results
                        if "results" in result and isinstance(result["results"], list):
                            # Combine all page results into a single markdown
                            markdown_content = ""
                            for page_result in result["results"]:
                                if isinstance(page_result, dict) and "result" in page_result:
                                    page_content = page_result["result"]
                                    if page_content:
                                        markdown_content += page_content + "\n\n<--- Page Split --->\n\n"
                            return markdown_content.strip()
                        
                        # Try common response field names
                        for field in ["markdown", "content", "text", "result", "output"]:
                            if field in result:
                                return result[field]
                        
                        # If no standard field, return the whole response as string
                        return json.dumps(result, indent=2)
                    else:
                        return str(result)
                else:
                    logger.error(f"API request failed with status {response.status_code}: {response.text}")
                    return None
            
        except Exception as e:
            logger.error(f"Error processing {pdf_path}: {str(e)}")
            return None
    
    def convert_pdf_to_markdown(self, pdf_path: str) -> Optional[str]:
        """
        Convert a single PDF file to Markdown
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Path to the generated Markdown file, or None if conversion failed
        """
        try:
            logger.info(f"Processing PDF: {pdf_path}")
            
            # Call OCR API
            markdown_content = self._call_ocr_api(pdf_path)
            
            if not markdown_content:
                logger.error(f"Failed to get markdown content for {pdf_path}")
                return None
            
            # Save markdown file with -MD suffix
            pdf_path_obj = Path(pdf_path)
            markdown_path = pdf_path_obj.with_name(f"{pdf_path_obj.stem}-MD.md")
            
            with open(markdown_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            logger.info(f"Successfully converted {pdf_path} to {markdown_path}")
            return str(markdown_path)
            
        except Exception as e:
            logger.error(f"Error converting {pdf_path}: {str(e)}")
            return None
    
    def scan_and_process_all_pdfs(self) -> List[str]:
        """
        Scan the data folder for PDF files and convert all of them to Markdown
        Recursively searches all subdirectories within the data folder.
        Processes PDFs in parallel batches using ThreadPoolExecutor.
        
        Returns:
            List of paths to generated Markdown files
        """
        # Find all PDF files in the data folder and subdirectories (recursive)
        pdf_files = list(self.data_folder.glob("**/*.pdf"))
        
        if not pdf_files:
            logger.info(f"No PDF files found in {self.data_folder}")
            return []
        
        logger.info(f"Found {len(pdf_files)} PDF files to process with {self.max_workers} concurrent workers")
        
        markdown_files = []
        
        # Process PDFs in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_pdf = {
                executor.submit(self.convert_pdf_to_markdown, str(pdf_file)): pdf_file 
                for pdf_file in pdf_files
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_pdf):
                pdf_file = future_to_pdf[future]
                try:
                    markdown_file = future.result()
                    if markdown_file:
                        markdown_files.append(markdown_file)
                except Exception as e:
                    logger.error(f"Exception processing {pdf_file}: {str(e)}")
        
        return markdown_files


def main():
    """Main function to run the PDF processor"""
    print(f"{Colors.BLUE}PDF to Markdown Processor{Colors.RESET}")
    print(f"{Colors.YELLOW}Scanning /data folder for PDF files...{Colors.RESET}")
    
    try:
        processor = PDFToMarkdownProcessor()
        markdown_files = processor.scan_and_process_all_pdfs()
        
        if markdown_files:
            print(f"\n{Colors.GREEN}Successfully converted {len(markdown_files)} PDF files to Markdown:{Colors.RESET}")
            for md_file in markdown_files:
                print(f"  - {md_file}")
        else:
            print(f"{Colors.YELLOW}No PDF files were processed.{Colors.RESET}")
            
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        print(f"{Colors.RED}Error: {str(e)}{Colors.RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()