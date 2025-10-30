"""API routes for bank statement processing."""

import asyncio
import logging
import tempfile
import shutil
from pathlib import Path
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException, status

from utils.config import settings
from models import BatchResponse, ProcessingSummary, FileResult, HealthResponse
from services.llm_service import llm_service
from services.pdf_service import pdf_service
from services.graph_workflow import bank_statement_workflow

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        llm_provider="openai"
    )


@router.post("/process", response_model=BatchResponse)
async def process_statements(
    files: List[UploadFile] = File(..., description="Bank statement PDF files or ZIP archives containing PDFs")
):
    """
    Process multiple bank statement PDFs or ZIP files containing PDFs.
    
    Accepts:
    - Individual PDF files
    - ZIP archives containing multiple PDFs
    - Mix of both
    
    Uses LLM to directly read and extract from PDFs:
    - statement_period
    - total_credits
    - total_debits
    
    Returns aggregated results with grand totals.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided"
        )
    
    # Log all uploaded files
    logger.info(f"Received {len(files)} file(s) in request")
    for idx, f in enumerate(files):
        logger.info(f"  Upload {idx+1}: {f.filename} (content_type: {f.content_type})")
    
    # Create upload directory if it doesn't exist
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(exist_ok=True)
    
    results: List[FileResult] = []
    grand_total_credits = 0.0
    grand_total_debits = 0.0
    total_processed = 0
    total_failed = 0
    
    # Collect all PDFs to process (from direct uploads and zip files)
    pdfs_to_process = []  # List of tuples: (display_name, file_path, cleanup_needed)
    temp_dirs_to_cleanup = []
    
    for upload_file in files:
        file_name = upload_file.filename or "unknown"
        temp_path = None
        
        try:
            # Save uploaded file temporarily
            temp_path = upload_dir / file_name
            with open(temp_path, "wb") as buffer:
                content = await upload_file.read()
                file_size = len(content)
                buffer.write(content)
            
            # Check if it's a ZIP file
            if pdf_service.is_zip_file(str(temp_path)):
                logger.info(f"Processing ZIP file: {file_name}")
                
                # Create temporary directory for extraction
                temp_extract_dir = tempfile.mkdtemp(prefix="zip_extract_")
                temp_dirs_to_cleanup.append(temp_extract_dir)
                
                try:
                    # Extract PDFs from zip
                    extracted_pdfs = pdf_service.extract_pdfs_from_zip(
                        str(temp_path), 
                        temp_extract_dir
                    )
                    
                    if not extracted_pdfs:
                        results.append(FileResult(
                            file_name=file_name,
                            status="failed",
                            error="No PDF files found in ZIP archive"
                        ))
                        total_failed += 1
                    else:
                        # Add extracted PDFs to processing queue
                        logger.info(f"Extracted {len(extracted_pdfs)} PDFs from {file_name}")
                        for original_name, extracted_path in extracted_pdfs:
                            logger.info(f"Adding to queue: {original_name} from {file_name}")
                            # Get file size for each extracted PDF
                            extracted_size = Path(extracted_path).stat().st_size
                            pdfs_to_process.append((original_name, extracted_path, False, extracted_size))
                    
                except Exception as e:
                    logger.error(f"Error extracting ZIP {file_name}: {e}")
                    results.append(FileResult(
                        file_name=file_name,
                        status="failed",
                        error=f"ZIP extraction error: {str(e)}"
                    ))
                    total_failed += 1
                
                # Clean up the zip file
                if temp_path and temp_path.exists():
                    temp_path.unlink()
                    
            elif file_name.lower().endswith('.pdf'):
                # It's a direct PDF upload
                pdfs_to_process.append((file_name, str(temp_path), True, file_size))
            else:
                # Unsupported file type - let workflow handle this
                pdfs_to_process.append((file_name, str(temp_path), True, file_size))
                    
        except Exception as e:
            logger.error(f"Error handling upload {file_name}: {e}")
            results.append(FileResult(
                file_name=file_name,
                status="failed",
                error=f"Upload error: {str(e)}"
            ))
            total_failed += 1
            if temp_path and temp_path.exists():
                temp_path.unlink()
    
    # Now process all collected PDFs SEQUENTIALLY using LangGraph workflow
    logger.info(f"Processing queue contains {len(pdfs_to_process)} PDFs")
    logger.info("=" * 80)
    
    for idx, (display_name, pdf_path, cleanup_needed, file_size) in enumerate(pdfs_to_process):
        logger.info(f"\n{'='*80}")
        logger.info(f"STARTING PROCESSING: PDF {idx+1}/{len(pdfs_to_process)}: {display_name}")
        logger.info(f"{'='*80}")
        
        try:
            # Process PDF through LangGraph workflow (includes file validation)
            result = await bank_statement_workflow.process_pdf(display_name, pdf_path, file_size)
            
            results.append(result)
            
            # Update totals
            if result.status == "processed" and result.data:
                grand_total_credits += result.data.total_credits
                grand_total_debits += result.data.total_debits
                total_processed += 1
            else:
                total_failed += 1
            
            logger.info(f"COMPLETED: {display_name}")
            logger.info(f"{'='*80}\n")
            
            # Add small delay between PDFs to ensure LLM fully completes
            if idx < len(pdfs_to_process) - 1:  # Don't delay after last file
                logger.info("Waiting 2 seconds before next PDF...")
                await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"Error processing {display_name}: {e}")
            results.append(FileResult(
                file_name=display_name,
                status="failed",
                error=f"Processing error: {str(e)}"
            ))
            total_failed += 1
        
        finally:
            # Clean up temporary file if it was a direct upload
            if cleanup_needed:
                try:
                    Path(pdf_path).unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {pdf_path}: {e}")
    
    # Clean up temporary extraction directories
    for temp_dir in temp_dirs_to_cleanup:
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning(f"Failed to delete temp directory {temp_dir}: {e}")
    
    # # Round grand totals
    # grand_total_credits = round(grand_total_credits, 2)
    # grand_total_debits = round(grand_total_debits, 2)
    
    summary = ProcessingSummary(
        grand_total_credits=grand_total_credits,
        grand_total_debits=grand_total_debits,
        total_files_processed=total_processed,
        total_files_failed=total_failed,
        files=results
    )
    
    return BatchResponse(summary=summary)


@router.post("/process-single", response_model=FileResult)
async def process_single_statement(
    file: UploadFile = File(..., description="Bank statement PDF file")
):
    """
    Process a single bank statement PDF.
    
    Convenience endpoint for processing one file at a time.
    """
    result = await process_statements(files=[file])
    
    if result.summary.files:
        return result.summary.files[0]
    
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to process file"
    )
