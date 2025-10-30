from pydantic import BaseModel
from typing import Optional, Literal, List


class StatementData(BaseModel):
    """Extracted statement data."""
    statement_period: str
    total_credits: float
    total_debits: float
    calculation_note: Optional[str] = None


class FileResult(BaseModel):
    """Result for a single file."""
    file_name: str
    status: Literal["processed", "failed"]
    data: Optional[StatementData] = None
    error: Optional[str] = None


class ProcessingSummary(BaseModel):
    """Summary of batch processing."""
    grand_total_credits: float
    grand_total_debits: float
    total_files_processed: int
    total_files_failed: int
    files: List[FileResult]


class BatchResponse(BaseModel):
    """Top-level response for batch processing."""
    summary: ProcessingSummary


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    llm_provider: str
    version: str = "1.0.0"
