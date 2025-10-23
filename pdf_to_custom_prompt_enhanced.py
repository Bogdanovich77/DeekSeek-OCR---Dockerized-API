#!/usr/bin/env python3
"""
PDF to Custom Prompt Processor (Enhanced)

This application scans the /data folder for PDF files and converts them to Markdown format
using the DeepSeek OCR API at localhost:8000 with a custom prompt loaded from
custom_prompt.yaml in the project root.

Enhanced version includes post-processing steps from run_dpsk_ocr_pdf.py:
- Special token cleanup
- Reference processing for layout information
- Image extraction and markdown link generation
- Content cleaning and formatting
"""

import os
import sys
import glob
import logging
import base64
import json
import requests
import yaml
import re
import io
import tempfile
import urllib.parse
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from PIL import Image, ImageDraw
import numpy as np
import fitz  # PyMuPDF

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


class PDFToCustomPromptProcessor:
    """Processor for converting PDF files to Markdown using DeepSeek OCR API with custom prompt and enhanced post-processing"""
    
    def __init__(self, data_folder: str = "data", api_base_url: str = "http://localhost:8000",
                 custom_prompt_file: str = "custom_prompt.yaml", extract_images: bool = True,
                 create_images_folder: bool = True):
        """
        Initialize the PDF processor
        
        Args:
            data_folder: Path to the folder containing PDF files
            api_base_url: Base URL of the DeepSeek OCR API
            custom_prompt_file: Path to the YAML file containing the custom prompt
            extract_images: Whether to extract images from the PDF
            create_images_folder: Whether to create an images subfolder for extracted images
        """
        self.data_folder = Path(data_folder)
        self.data_folder.mkdir(exist_ok=True)
        self.api_base_url = api_base_url
        self.custom_prompt_file = custom_prompt_file
        self.extract_images = extract_images
        self.create_images_folder = create_images_folder
        
        # Create images subfolder if needed
        if self.extract_images and self.create_images_folder:
            self.images_folder = self.data_folder / "images"
            self.images_folder.mkdir(exist_ok=True)
        else:
            self.images_folder = None
        
        # Load custom prompt from YAML file
        self.custom_prompt = self._load_custom_prompt()
        
        # Test API connection
        if not self._test_api_connection():
            raise ConnectionError(f"Cannot connect to API at {api_base_url}")
    
    def _load_custom_prompt(self) -> str:
        """
        Load custom prompt from YAML file
        
        Returns:
            The custom prompt string
            
        Raises:
            FileNotFoundError: If the custom prompt file doesn't exist
            yaml.YAMLError: If the YAML file is malformed
            KeyError: If the prompt key is not found in the YAML file
        """
        try:
            with open(self.custom_prompt_file, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                
            if 'prompt' not in config:
                raise KeyError(f"'prompt' key not found in {self.custom_prompt_file}")
                
            prompt = config['prompt']
            logger.info(f"Loaded custom prompt from {self.custom_prompt_file}: {prompt}")
            return prompt
            
        except FileNotFoundError:
            logger.error(f"Custom prompt file not found: {self.custom_prompt_file}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing {self.custom_prompt_file}: {str(e)}")
            raise
        except KeyError as e:
            logger.error(f"Missing required key in {self.custom_prompt_file}: {str(e)}")
            raise
    
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
    
    def _pdf_to_images(self, pdf_path: str, dpi: int = 144) -> List[Image.Image]:
        """
        Convert PDF pages to PIL Images
        
        Args:
            pdf_path: Path to the PDF file
            dpi: Resolution for conversion
            
        Returns:
            List of PIL Images
        """
        images = []
        
        try:
            pdf_document = fitz.open(pdf_path)
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
        except Exception as e:
            logger.error(f"Error converting PDF to images: {str(e)}")
        
        return images
    
    def _re_match(self, text: str) -> Tuple[List, List, List]:
        """
        Match reference patterns in the text
        
        Args:
            text: The text to search for patterns
            
        Returns:
            Tuple of (all_matches, image_matches, other_matches)
        """
        pattern = r'(<\|ref\|>(.*?)<\|/ref\|><\|det\|>(.*?)<\|/det\|>)'
        matches = re.findall(pattern, text, re.DOTALL)
        
        matches_image = []
        matches_other = []
        
        for a_match in matches:
            if '<|ref|>image<|/ref|>' in a_match[0]:
                matches_image.append(a_match[0])
            else:
                matches_other.append(a_match[0])
        
        return matches, matches_image, matches_other
    
    def _extract_coordinates_and_label(self, ref_text: Tuple) -> Optional[Tuple[str, List]]:
        """
        Extract coordinates and label from reference text
        
        Args:
            ref_text: Reference text tuple from regex match
            
        Returns:
            Tuple of (label_type, coordinates_list) or None if extraction fails
        """
        try:
            label_type = ref_text[1]
            cor_list = eval(ref_text[2])
            return (label_type, cor_list)
        except Exception as e:
            logger.error(f"Error extracting coordinates: {str(e)}")
            return None
    
    def _extract_and_save_images(self, pdf_path: str, content: str, page_idx: int) -> Tuple[str, int]:
        """
        Extract images from content and save them to the images folder
        
        Args:
            pdf_path: Path to the original PDF file
            content: The OCR content with reference tags
            page_idx: Index of the page being processed
            
        Returns:
            Tuple of (processed_content, number_of_images_extracted)
        """
        if not self.extract_images or not self.images_folder:
            return content, 0
        
        # Get PDF images for this page
        pdf_images = self._pdf_to_images(pdf_path)
        if page_idx >= len(pdf_images):
            return content, 0
        
        page_image = pdf_images[page_idx]
        image_width, image_height = page_image.size
        
        # Find all image references
        _, matches_images, _ = self._re_match(content)
        img_idx = 0
        
        for idx, a_match_image in enumerate(matches_images):
            try:
                # Extract the reference text
                pattern = r'<\|ref\|>image<\|/ref\|><\|det\|>(.*?)<\|/det\|>'
                det_match = re.search(pattern, a_match_image)
                
                if det_match:
                    det_content = det_match.group(1)
                    try:
                        coordinates = eval(det_content)
                        
                        # Extract and save the image
                        for points in coordinates:
                            x1, y1, x2, y2 = points
                            
                            # Scale coordinates to actual image size
                            x1 = int(x1 / 999 * image_width)
                            y1 = int(y1 / 999 * image_height)
                            x2 = int(x2 / 999 * image_width)
                            y2 = int(y2 / 999 * image_height)
                            
                            # Crop and save the image
                            cropped = page_image.crop((x1, y1, x2, y2))
                            image_filename = f"{Path(pdf_path).stem}_page{page_idx}_{img_idx}.jpg"
                            image_path = self.images_folder / image_filename
                            cropped.save(image_path)
                            
                            # Replace reference with markdown link with URL-encoded filename
                            # The images folder is relative to the markdown file location
                            encoded_filename = urllib.parse.quote(image_filename)
                            markdown_link = f"![](images/{encoded_filename})\n"
                            content = content.replace(a_match_image, markdown_link, 1)
                            
                            img_idx += 1
                            break
                    except Exception as e:
                        logger.error(f"Error processing image coordinates: {str(e)}")
                        # If we can't process the coordinates, just remove the tag
                        content = content.replace(a_match_image, "", 1)
            except Exception as e:
                logger.error(f"Error extracting image: {str(e)}")
                content = content.replace(a_match_image, "", 1)
        
        return content, img_idx
    
    def _clean_content(self, content: str) -> str:
        """
        Clean up the OCR content
        
        Args:
            content: Raw OCR content
            
        Returns:
            Cleaned content
        """
        # Remove end of sentence tokens
        if '<｜end▁of▁sentence｜>' in content:
            content = content.replace('<｜end▁of▁sentence｜>', '')
        
        # Get all non-image references
        _, _, matches_other = self._re_match(content)
        
        # Remove other reference tags and clean up
        for idx, a_match_other in enumerate(matches_other):
            content = content.replace(a_match_other, '')
        
        # Replace special LaTeX-like symbols
        content = content.replace('\\coloneqq', ':=')
        content = content.replace('\\eqqcolon', '=:')
        
        # Clean up excessive newlines
        content = content.replace('\n\n\n\n', '\n\n')
        content = content.replace('\n\n\n', '\n\n')
        
        return content.strip()
    
    def _process_page_content(self, pdf_path: str, content: str, page_idx: int) -> str:
        """
        Process a single page's content with all post-processing steps
        
        Args:
            pdf_path: Path to the original PDF file
            content: Raw OCR content for the page
            page_idx: Index of the page being processed
            
        Returns:
            Processed content
        """
        # Step 1: Extract and save images
        content, num_images = self._extract_and_save_images(pdf_path, content, page_idx)
        
        # Step 2: Clean up the content
        content = self._clean_content(content)
        
        # Step 3: Add page separator
        page_separator = '\n\n<--- Page Split --->\n\n'
        content += page_separator
        
        logger.info(f"Processed page {page_idx + 1}, extracted {num_images} images")
        
        return content
    
    def _call_ocr_api(self, pdf_path: str) -> Optional[str]:
        """
        Call the OCR API to process a PDF file using the custom prompt
        
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
                
                # Use custom prompt from YAML file
                data = {'prompt': self.custom_prompt}
                
                response = requests.post(url, files=files, data=data, timeout=300)
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Successfully processed PDF using endpoint: {endpoint}")
                    
                    # Extract markdown content from BatchOCRResponse
                    if isinstance(result, dict):
                        # Check if this is a batch response with results
                        if "results" in result and isinstance(result["results"], list):
                            # Process each page with post-processing
                            processed_content = ""
                            for page_idx, page_result in enumerate(result["results"]):
                                if isinstance(page_result, dict) and "result" in page_result:
                                    page_content = page_result["result"]
                                    if page_content:
                                        # Apply post-processing to each page
                                        processed_page = self._process_page_content(
                                            pdf_path, page_content, page_idx
                                        )
                                        processed_content += processed_page
                            
                            return processed_content.strip()
                        
                        # Try common response field names
                        for field in ["markdown", "content", "text", "result", "output"]:
                            if field in result:
                                # Single page processing
                                return self._process_page_content(pdf_path, result[field], 0)
                        
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
            
            # Save markdown file with -CUSTOM suffix
            pdf_path_obj = Path(pdf_path)
            markdown_path = pdf_path_obj.with_name(f"{pdf_path_obj.stem}-CUSTOM.md")
            
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
        
        Returns:
            List of paths to generated Markdown files
        """
        # Find all PDF files in the data folder
        pdf_files = list(self.data_folder.glob("*.pdf"))
        
        if not pdf_files:
            logger.info(f"No PDF files found in {self.data_folder}")
            return []
        
        logger.info(f"Found {len(pdf_files)} PDF files to process")
        
        markdown_files = []
        for pdf_file in pdf_files:
            markdown_file = self.convert_pdf_to_markdown(str(pdf_file))
            if markdown_file:
                markdown_files.append(markdown_file)
        
        return markdown_files


def main():
    """Main function to run the PDF processor"""
    print(f"{Colors.BLUE}PDF to Custom Prompt Processor (Enhanced){Colors.RESET}")
    print(f"{Colors.YELLOW}Scanning /data folder for PDF files...{Colors.RESET}")
    
    try:
        processor = PDFToCustomPromptProcessor(
            extract_images=True,
            create_images_folder=True
        )
        markdown_files = processor.scan_and_process_all_pdfs()
        
        if markdown_files:
            print(f"\n{Colors.GREEN}Successfully converted {len(markdown_files)} PDF files to Markdown:{Colors.RESET}")
            for md_file in markdown_files:
                print(f"  - {md_file}")
            print(f"\n{Colors.BLUE}Used custom prompt: {processor.custom_prompt}{Colors.RESET}")
            if processor.extract_images:
                print(f"\n{Colors.BLUE}Images extracted to: {processor.images_folder}{Colors.RESET}")
        else:
            print(f"{Colors.YELLOW}No PDF files were processed.{Colors.RESET}")
            
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        print(f"{Colors.RED}Error: {str(e)}{Colors.RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()