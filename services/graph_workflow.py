"""LangGraph workflow for processing bank statements."""

import logging
import tempfile
import shutil
from pathlib import Path
from typing import TypedDict, Annotated, Literal
from operator import add

from fastapi import UploadFile
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage

from models.models import FileResult, StatementData
from services.pdf_service import pdf_service
from services.llm_service import llm_service
from utils.config import settings

logger = logging.getLogger(__name__)


# Define the state schema
class BankStatementState(TypedDict):
    """State for bank statement processing workflow."""
    # Input
    file_name: str
    pdf_path: str
    upload_file: UploadFile | None  # For initial upload handling
    
    # File handling
    file_size: int
    is_zip: bool
    extracted_pdfs: list[tuple[str, str]]  # List of (name, path) for ZIP contents
    temp_dirs: list[str]  # Temp directories to cleanup
    
    # Processing state
    is_valid: bool
    image_base64_list: list[str]
    
    # Output
    status: Literal["pending", "processing", "processed", "failed"]
    result: FileResult | None
    error: str | None
    
    # Metadata
    current_step: str


class BankStatementWorkflow:
    """LangGraph workflow for processing bank statements."""
    
    def __init__(self):
        """Initialize the workflow graph."""
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        # Create the graph
        workflow = StateGraph(BankStatementState)
        
        # Add nodes (processing steps)
        workflow.add_node("check_file_type", self._check_file_type_node)
        workflow.add_node("validate_pdf", self._validate_pdf_node)
        workflow.add_node("convert_to_images", self._convert_to_images_node)
        workflow.add_node("extract_data", self._extract_data_node)
        workflow.add_node("handle_error", self._handle_error_node)
        
        # Define the workflow edges
        workflow.set_entry_point("check_file_type")
        
        # From check_file_type: go to validate_pdf if ok, else error
        workflow.add_conditional_edges(
            "check_file_type",
            self._should_continue_after_file_check,
            {
                "continue": "validate_pdf",
                "error": "handle_error"
            }
        )
        
        # From validate_pdf: go to convert_to_images if valid, else error
        workflow.add_conditional_edges(
            "validate_pdf",
            self._should_continue_after_validation,
            {
                "continue": "convert_to_images",
                "error": "handle_error"
            }
        )
        
        # From convert_to_images: go to extract_data if successful, else error
        workflow.add_conditional_edges(
            "convert_to_images",
            self._should_continue_after_conversion,
            {
                "continue": "extract_data",
                "error": "handle_error"
            }
        )
        
        # From extract_data: always end (result is in state)
        workflow.add_edge("extract_data", END)
        
        # From handle_error: always end
        workflow.add_edge("handle_error", END)
        
        return workflow.compile()
    
    # Node functions
    async def _check_file_type_node(self, state: BankStatementState) -> BankStatementState:
        """Node: Check file type, size, and handle ZIP extraction."""
        logger.info(f"[{state['file_name']}] Node: check_file_type")
        
        try:
            # Check file size
            if state.get("file_size", 0) > settings.max_file_size:
                logger.warning(f"[{state['file_name']}] ✗ File size exceeds limit")
                return {
                    **state,
                    "current_step": "check_file_type",
                    "status": "failed",
                    "error": f"File size exceeds maximum of {settings.max_file_size} bytes"
                }
            
            # Check if file is a PDF
            if state["file_name"].lower().endswith('.pdf'):
                logger.info(f"[{state['file_name']}] ✓ Valid PDF file")
                return {
                    **state,
                    "is_zip": False,
                    "current_step": "check_file_type",
                    "status": "processing"
                }
            
            # Check if file is a ZIP (this would be handled differently in batch processing)
            elif state["file_name"].lower().endswith('.zip'):
                logger.info(f"[{state['file_name']}] ✓ ZIP file detected")
                return {
                    **state,
                    "is_zip": True,
                    "current_step": "check_file_type",
                    "status": "processing"
                }
            
            # Unsupported file type
            else:
                logger.warning(f"[{state['file_name']}] ✗ Unsupported file type")
                return {
                    **state,
                    "current_step": "check_file_type",
                    "status": "failed",
                    "error": "Only PDF and ZIP files are supported"
                }
                
        except Exception as e:
            logger.error(f"[{state['file_name']}] Error in check_file_type: {e}")
            return {
                **state,
                "current_step": "check_file_type",
                "status": "failed",
                "error": f"File check error: {str(e)}"
            }
    
    async def _validate_pdf_node(self, state: BankStatementState) -> BankStatementState:
        """Node: Validate the PDF file."""
        logger.info(f"[{state['file_name']}] Node: validate_pdf")
        
        try:
            is_valid = pdf_service.validate_pdf(state["pdf_path"])
            
            if is_valid:
                logger.info(f"[{state['file_name']}] ✓ PDF validation passed")
                return {
                    **state,
                    "is_valid": True,
                    "current_step": "validate_pdf",
                    "status": "processing"
                }
            else:
                logger.warning(f"[{state['file_name']}] ✗ PDF validation failed")
                return {
                    **state,
                    "is_valid": False,
                    "current_step": "validate_pdf",
                    "status": "failed",
                    "error": "Invalid or corrupted PDF file"
                }
        except Exception as e:
            logger.error(f"[{state['file_name']}] Error in validate_pdf: {e}")
            return {
                **state,
                "is_valid": False,
                "current_step": "validate_pdf",
                "status": "failed",
                "error": f"Validation error: {str(e)}"
            }
    
    async def _convert_to_images_node(self, state: BankStatementState) -> BankStatementState:
        """Node: Convert PDF to images."""
        logger.info(f"[{state['file_name']}] Node: convert_to_images")
        
        try:
            image_base64_list = await pdf_service.read_pdf_as_images(state["pdf_path"])
            logger.info(f"[{state['file_name']}] ✓ Converted to {len(image_base64_list)} images")
            
            return {
                **state,
                "image_base64_list": image_base64_list,
                "current_step": "convert_to_images",
                "status": "processing"
            }
        except Exception as e:
            logger.error(f"[{state['file_name']}] Error in convert_to_images: {e}")
            return {
                **state,
                "current_step": "convert_to_images",
                "status": "failed",
                "error": f"Image conversion error: {str(e)}"
            }
    
    async def _extract_data_node(self, state: BankStatementState) -> BankStatementState:
        """Node: Extract data using LLM."""
        logger.info(f"[{state['file_name']}] Node: extract_data")
        
        try:
            result = await llm_service.process_pdf(
                state["file_name"],
                state["image_base64_list"]
            )
            
            if result.status == "processed":
                logger.info(f"[{state['file_name']}] ✓ Data extraction successful")
                if result.data:
                    logger.info(f"[{state['file_name']}]   Period: {result.data.statement_period}")
                    logger.info(f"[{state['file_name']}]   Credits: RM {result.data.total_credits}")
                    logger.info(f"[{state['file_name']}]   Debits: RM {result.data.total_debits}")
            else:
                logger.warning(f"[{state['file_name']}] ✗ Data extraction failed: {result.error}")
            
            return {
                **state,
                "result": result,
                "current_step": "extract_data",
                "status": result.status
            }
        except Exception as e:
            logger.error(f"[{state['file_name']}] Error in extract_data: {e}")
            error_result = FileResult(
                file_name=state["file_name"],
                status="failed",
                error=f"Extraction error: {str(e)}"
            )
            return {
                **state,
                "result": error_result,
                "current_step": "extract_data",
                "status": "failed",
                "error": str(e)
            }
    
    async def _handle_error_node(self, state: BankStatementState) -> BankStatementState:
        """Node: Handle errors and create error result."""
        logger.info(f"[{state['file_name']}] Node: handle_error")
        
        error_result = FileResult(
            file_name=state["file_name"],
            status="failed",
            error=state.get("error", "Unknown error occurred")
        )
        
        return {
            **state,
            "result": error_result,
            "status": "failed"
        }
    
    # Conditional edge functions
    def _should_continue_after_file_check(self, state: BankStatementState) -> str:
        """Decide next step after file type check."""
        if state.get("status") == "failed":
            return "error"
        # Only continue if it's a PDF (ZIP handling is done in routes)
        if not state.get("is_zip", False):
            return "continue"
        return "error"
    
    def _should_continue_after_validation(self, state: BankStatementState) -> str:
        """Decide next step after PDF validation."""
        if state.get("is_valid", False):
            return "continue"
        return "error"
    
    def _should_continue_after_conversion(self, state: BankStatementState) -> str:
        """Decide next step after image conversion."""
        if state.get("image_base64_list") and state["status"] != "failed":
            return "continue"
        return "error"
    
    async def process_pdf(self, file_name: str, pdf_path: str, file_size: int = 0) -> FileResult:
        """
        Process a single PDF through the workflow.
        
        Args:
            file_name: Display name of the file
            pdf_path: Path to the PDF file
            file_size: Size of the file in bytes
            
        Returns:
            FileResult with processing outcome
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"Starting LangGraph workflow for: {file_name}")
        logger.info(f"{'='*80}")
        
        # Initialize state
        initial_state: BankStatementState = {
            "file_name": file_name,
            "pdf_path": pdf_path,
            "upload_file": None,
            "file_size": file_size,
            "is_zip": False,
            "extracted_pdfs": [],
            "temp_dirs": [],
            "is_valid": False,
            "image_base64_list": [],
            "status": "pending",
            "result": None,
            "error": None,
            "current_step": "init"
        }
        
        # Run the workflow
        final_state = await self.graph.ainvoke(initial_state)
        
        logger.info(f"{'='*80}")
        logger.info(f"Workflow completed for: {file_name}")
        logger.info(f"Final status: {final_state['status']}")
        logger.info(f"{'='*80}\n")
        
        # Return the result
        result = final_state.get("result")
        if result:
            return result
        
        # Fallback if no result was created
        return FileResult(
            file_name=file_name,
            status="failed",
            error="Workflow completed but no result was generated"
        )


# Singleton instance
bank_statement_workflow = BankStatementWorkflow()
