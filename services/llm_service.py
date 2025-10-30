"""LLM service for processing bank statements with OpenAI."""

import json
import logging
from openai import AsyncOpenAI

from utils.config import settings
from models.models import FileResult, StatementData
from utils.prompts import SYSTEM_PROMPT, get_user_prompt

logger = logging.getLogger(__name__)


class LLMService:
    """OpenAI LLM service for processing bank statement PDFs."""
    
    def __init__(self):
        # For LM Studio, API key is not required
        if settings.llm_provider == "openai" and not settings.openai_api_key:
            raise ValueError("OpenAI API key not configured")
        
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url
        )
        self.model = settings.openai_model
        self.provider = settings.llm_provider
        logger.info(f"Initialized {self.provider} with model {self.model} at {settings.openai_base_url}")
    
    async def process_pdf(self, file_name: str, image_base64_list: list[str]) -> FileResult:
        """Process a PDF (converted to images) using vision model."""
        try:
            import uuid
            import time
            
            # Generate unique request ID to prevent caching
            request_id = str(uuid.uuid4())[:8]
            timestamp = int(time.time())
            
            user_prompt = get_user_prompt(file_name, "")
            
            # Build content array with text prompt and all page images
            content = [
                {
                    "type": "text",
                    "text": f"""REQUEST ID: {request_id} | TIMESTAMP: {timestamp}

THIS IS A NEW DOCUMENT. DO NOT USE ANY PREVIOUS VALUES.

Analyze this bank statement and extract the required information.

{user_prompt}"""
                }
            ]
            
            # Add each page as an image
            for i, img_base64 in enumerate(image_base64_list):
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_base64}"
                    }
                })
                logger.info(f"Added page {i+1}/{len(image_base64_list)} to LLM request")
            
            # Use vision model
            # Note: temperature=0.3 to reduce caching/determinism while maintaining accuracy
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                temperature=0.0,
                max_tokens=2048,
                seed=timestamp  # Use timestamp as seed for variation
            )
            
            content = response.choices[0].message.content
            if not content:
                return FileResult(
                    file_name=file_name,
                    status="failed",
                    error="Empty response from OpenAI"
                )
            
            # Log raw LLM response for debugging
            logger.info(f"Raw LLM response for {file_name}: {content[:500]}...")
            
            # Extract JSON from response
            result_data = self._extract_json(content)
            return self._parse_llm_response(file_name, result_data)
            
        except Exception as e:
            logger.error(f"Error processing {file_name}: {e}")
            return FileResult(
                file_name=file_name,
                status="failed",
                error=f"Processing error: {str(e)}"
            )
    
    def _extract_json(self, content: str) -> dict:
        """Extract JSON from LLM response."""
        try:
            # Try direct JSON parse
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            content = content.strip()
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()
            
            return json.loads(content)
    
    def _parse_llm_response(self, file_name: str, result_data: dict) -> FileResult:
        """Parse and validate LLM response."""
        try:
            status = result_data.get("status")
            
            if status == "processed":
                data_dict = result_data.get("data", {})
                statement_data = StatementData(
                    statement_period=data_dict["statement_period"],
                    total_credits=round(float(data_dict["total_credits"]), 2),
                    total_debits=round(float(data_dict["total_debits"]), 2),
                    calculation_note=data_dict.get("calculation_note")
                )
                return FileResult(
                    file_name=file_name,
                    status="processed",
                    data=statement_data
                )
            elif status == "failed":
                return FileResult(
                    file_name=file_name,
                    status="failed",
                    error=result_data.get("error", "Unknown error")
                )
            else:
                return FileResult(
                    file_name=file_name,
                    status="failed",
                    error="Invalid status in LLM response"
                )
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error parsing LLM response for {file_name}: {e}")
            return FileResult(
                file_name=file_name,
                status="failed",
                error="Failed to parse LLM response"
            )


# Singleton instance
llm_service = LLMService()
