"""PDF service for reading PDF files with LLM."""

import logging
import base64
import zipfile
import tempfile
import io
from pathlib import Path
from typing import List, Tuple
from pdf2image import convert_from_path
from PIL import Image

logger = logging.getLogger(__name__)


class PDFService:
    """Service for reading PDF files."""
    
    async def read_pdf_as_images(self, pdf_path: str) -> List[str]:
        """
        Convert PDF pages to images and return as base64 encoded strings.
        Each page becomes a separate PNG image.
        
        Returns:
            List of base64 encoded PNG images (one per page)
        """
        try:
            # Convert PDF pages to PIL Image objects
            # Using 300 DPI for better OCR quality (higher quality for vision models)
            images = convert_from_path(pdf_path, dpi=300, fmt='png')
            
            base64_images = []
            for i, image in enumerate(images):
                # Convert PIL Image to bytes
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='PNG', optimize=True)
                img_byte_arr.seek(0)
                
                # Encode to base64
                img_base64 = base64.b64encode(img_byte_arr.read()).decode('utf-8')
                base64_images.append(img_base64)
                
                logger.info(f"Converted page {i+1}/{len(images)} of {pdf_path}")
            
            logger.info(f"Successfully converted PDF to {len(base64_images)} image(s): {pdf_path}")
            return base64_images
            
        except Exception as e:
            logger.error(f"Error converting PDF to images {pdf_path}: {e}")
            raise
    
    def validate_pdf(self, pdf_path: str) -> bool:
        """Validate that the file exists and is readable."""
        try:
            path = Path(pdf_path)
            if not path.exists():
                logger.error(f"PDF file not found: {pdf_path}")
                return False
            
            if not path.is_file():
                logger.error(f"Path is not a file: {pdf_path}")
                return False
            
            # Check if file is readable
            with open(pdf_path, 'rb') as f:
                f.read(1024)  # Try reading first 1KB
            
            return True
            
        except Exception as e:
            logger.error(f"Invalid PDF {pdf_path}: {e}")
            return False
    
    def extract_pdfs_from_zip(self, zip_path: str, extract_dir: str) -> List[Tuple[str, str]]:
        """
        Extract PDF files from a zip archive.
        
        Args:
            zip_path: Path to the zip file
            extract_dir: Directory to extract PDFs to
            
        Returns:
            List of tuples (original_filename, extracted_path)
        """
        extracted_pdfs = []
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Get list of PDF files in the zip
                all_files = zip_ref.namelist()
                logger.info(f"Zip contains {len(all_files)} total files: {all_files}")
                
                pdf_files = [f for f in all_files 
                           if f.lower().endswith('.pdf') and not f.startswith('__MACOSX')]
                
                if not pdf_files:
                    logger.warning(f"No PDF files found in zip: {zip_path}")
                    return []
                
                logger.info(f"Found {len(pdf_files)} PDF(s) in zip file: {pdf_files}")
                
                # Extract each PDF
                for pdf_file in pdf_files:
                    try:
                        # Extract to temporary directory
                        extracted_path = zip_ref.extract(pdf_file, extract_dir)
                        
                        # Get just the filename (without directory structure)
                        original_name = Path(pdf_file).name
                        
                        extracted_pdfs.append((original_name, extracted_path))
                        logger.info(f"Extracted: {original_name}")
                        
                    except Exception as e:
                        logger.error(f"Failed to extract {pdf_file}: {e}")
                        continue
                
        except zipfile.BadZipFile:
            logger.error(f"Invalid zip file: {zip_path}")
            raise ValueError("Invalid or corrupted zip file")
        except Exception as e:
            logger.error(f"Error extracting zip {zip_path}: {e}")
            raise
        
        return extracted_pdfs
    
    def is_zip_file(self, file_path: str) -> bool:
        """Check if a file is a valid zip file."""
        try:
            return zipfile.is_zipfile(file_path)
        except Exception:
            return False


# Singleton instance
pdf_service = PDFService()
