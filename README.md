# Bank Statement Processor

A FastAPI-based service that extracts financial data from bank statement PDFs using OCR and Large Language Models (LLMs).

## 🎯 Architecture

This application uses **LangGraph** to orchestrate the processing workflow as a stateful graph with automatic error handling and routing.

### LangGraph Workflow

```
                    ┌─────────────────┐
                    │check_file_type  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  file_ok?       │
                    └────┬───────┬────┘
                    yes  │       │ no
                         │       │
              ┌──────────▼──┐   │
              │validate_pdf │   │
              └──────┬──────┘   │
                     │          │
              ┌──────▼──────┐   │
              │ is_valid?   │   │
              └──┬───────┬──┘   │
            yes  │       │ no   │
                 │       │      │
          ┌──────▼───┐  │      │
          │convert_  │  │      │
          │to_images │  │      │
          └──────┬───┘  │      │
                 │      │      │
          ┌──────▼───┐  │      │
          │success?  │  │      │
          └──┬────┬──┘  │      │
        yes  │    │ no  │      │
             │    │     │      │
      ┌──────▼─┐  │     │      │
      │extract_│  │     │      │
      │  data  │  │     │      │
      └────┬───┘  │     │      │
           │      │     │      │
           │   ┌──▼─────▼──────▼──┐
           │   │  handle_error    │
           │   └────────┬─────────┘
           │            │
           └────────────▼─────
                     END
```

**Workflow Steps:**
1. **Check File Type** - Validates file type (PDF/ZIP) and size limits
2. **Validate PDF** - Ensures PDF is readable and not corrupted
3. **Convert to Images** - Converts PDF pages to base64-encoded images
4. **Extract Data** - LLM analyzes images and extracts financial data
5. **Handle Error** - Centralized error handling with graceful fallback

## Features

- **🔄 LangGraph Workflow**: Stateful processing pipeline with automatic routing
- **Direct PDF Reading**: LLM reads PDF documents directly without OCR
- **ZIP File Support**: Upload ZIP archives containing multiple PDF bank statements
- **LLM Integration**: Supports OpenAI and LM Studio (local models)
- **Batch Processing**: Process multiple statements in a single request
- **Structured Output**: Returns JSON with validated financial data
- **Error Handling**: Graceful fallback for failed extractions with centralized error handling
- **Docker Support**: Easy deployment with Docker and docker-compose
- **Observable**: Clear logging of each workflow step

## Extracted Fields

For each bank statement, the service extracts:

- `statement_period`: Date range of the statement (string)
- `total_credits`: Sum of all credit transactions (float, 2 decimal places)
- `total_debits`: Sum of all debit transactions (float, 2 decimal places)
- `calculation_note`: Optional note when multiple candidates were combined

## Prerequisites

### For Docker (Recommended)

- **Docker** and **Docker Compose** installed
- **LM Studio** (optional, for local LLM) or **OpenAI API key**

### For Local Development

- **Python 3.9+**
- **LM Studio** (optional, for local LLM) or **OpenAI API key**

## Installation

1. **Clone the repository**
   ```bash
   cd /Users/aqiliman/Developer/PersonalProject/bank-statment-processor
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

## Configuration

Edit `.env` file:

```env
# LLM Configuration
LLM_PROVIDER=lmstudio
OPENAI_API_KEY=not-needed
OPENAI_MODEL=local-model
OPENAI_BASE_URL=http://host.docker.internal:1234/v1

# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=true
```

### LLM Provider Options

**Option 1: LM Studio (Local)**
```env
LLM_PROVIDER=lmstudio
OPENAI_API_KEY=not-needed
OPENAI_MODEL=your-model-name
OPENAI_BASE_URL=http://localhost:1234/v1  # or http://host.docker.internal:1234/v1 for Docker
```

**Option 2: OpenAI**
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4-turbo-preview
OPENAI_BASE_URL=https://api.openai.com/v1
```

## Running the Server

### Option 1: Docker Compose (Recommended)

1. **Create `.env` file**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

2. **Start the service**
   ```bash
   docker-compose up -d
   ```

3. **View logs**
   ```bash
   docker-compose logs -f
   ```

4. **Stop the service**
   ```bash
   docker-compose down
   ```

The API will be available at `http://localhost:8000`

### Option 2: Docker (Manual)

1. **Build the image**
   ```bash
   docker build -t bank-statement-processor .
   ```

2. **Run the container**
   ```bash
   docker run -d \
     --name bank-statement-processor \
     -p 8000:8000 \
     -v $(pwd)/uploads:/app/uploads \
     --env-file .env \
     bank-statement-processor
   ```

3. **View logs**
   ```bash
   docker logs -f bank-statement-processor
   ```

4. **Stop the container**
   ```bash
   docker stop bank-statement-processor
   docker rm bank-statement-processor
   ```

### Option 3: Local Development

**Development Mode**

```bash
python main.py
```

Or with uvicorn directly:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Production Mode**

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Endpoints

### Health Check

```bash
GET /api/v1/health
```

**Response:**
```json
{
  "status": "healthy",
  "llm_provider": "openai",
  "version": "1.0.0"
}
```

### Process Multiple Statements

```bash
POST /api/v1/process
Content-Type: multipart/form-data
```

**Request (Individual PDFs):**
```bash
curl -X POST "http://localhost:8000/api/v1/process" \
  -F "files=@statement1.pdf" \
  -F "files=@statement2.pdf" \
  -F "files=@statement3.pdf"
```

**Request (ZIP File):**
```bash
curl -X POST "http://localhost:8000/api/v1/process" \
  -F "files=@bank_statements.zip"
```

**Request (Mixed - PDFs and ZIP):**
```bash
curl -X POST "http://localhost:8000/api/v1/process" \
  -F "files=@statement1.pdf" \
  -F "files=@statements_batch.zip" \
  -F "files=@statement2.pdf"
```

**Response:**
```json
{
  "summary": {
    "grand_total_credits": 15750.75,
    "grand_total_debits": 8320.10,
    "total_files_processed": 2,
    "total_files_failed": 1,
    "files": [
      {
        "file_name": "statement1.pdf",
        "status": "processed",
        "data": {
          "statement_period": "Jan 1, 2024 to Jan 31, 2024",
          "total_credits": 10500.25,
          "total_debits": 4100.00
        }
      },
      {
        "file_name": "statement2.pdf",
        "status": "processed",
        "data": {
          "statement_period": "Feb 1, 2024 to Feb 29, 2024",
          "total_credits": 5250.50,
          "total_debits": 4220.10,
          "calculation_note": "Combined multiple credit sections"
        }
      },
      {
        "file_name": "statement3.pdf",
        "status": "failed",
        "error": "Could not reliably parse numeric tables from OCR text"
      }
    ]
  }
}
```

### Process Single Statement

```bash
POST /api/v1/process-single
Content-Type: multipart/form-data
```

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/process-single" \
  -F "file=@statement.pdf"
```

**Response:**
```json
{
  "file_name": "statement.pdf",
  "status": "processed",
  "data": {
    "statement_period": "Jan 1, 2024 to Jan 31, 2024",
    "total_credits": 10500.25,
    "total_debits": 4100.00
  }
}
```

## ZIP File Support

The API supports uploading ZIP archives containing multiple PDF bank statements:

### Features
- **Automatic Extraction**: ZIP files are automatically detected and extracted
- **Mixed Uploads**: You can upload a combination of PDF files and ZIP archives in the same request
- **Nested PDFs**: Extracts PDFs from any directory structure within the ZIP
- **Error Handling**: Individual PDF failures don't affect other files in the batch

### ZIP File Requirements
- Must be a valid ZIP archive
- Can contain one or more PDF files
- PDFs can be in subdirectories within the ZIP
- Maximum file size limit applies to the ZIP file itself
- macOS system files (`__MACOSX`) are automatically ignored

### Example ZIP Structure
```
bank_statements.zip
├── january_2024.pdf
├── february_2024.pdf
```

All PDFs will be extracted and processed individually, with results returned for each file.

## API Documentation

Interactive API documentation is available at:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Project Structure

```
bank-statment-processor/
├── .github/
│   └── workflows/
│       └── deploy.yml       # GitHub Actions deployment
├── models/
│   ├── __init__.py
│   └── models.py            # Pydantic models
├── routes/
│   ├── __init__.py
│   └── routes.py            # API endpoints
├── services/
│   ├── __init__.py
│   ├── graph_workflow.py    # LangGraph workflow orchestration
│   ├── llm_service.py       # LLM integration (OpenAI/LM Studio)
│   └── pdf_service.py       # PDF reading and conversion
├── utils/
│   ├── __init__.py
│   ├── config.py            # Configuration settings
│   └── prompts.py           # LLM prompt templates
├── .dockerignore            # Docker build exclusions
├── .env.example             # Environment template
├── .gitignore
├── Dockerfile               # Docker image definition
├── docker-compose.yml       # Docker compose configuration
├── example_response.json    # Example API response
├── main.py                  # FastAPI application entry point
├── README.md
├── requirements.txt         # Python dependencies
```

## Error Handling

The service handles various error scenarios:

- **Invalid PDF**: Returns error if file is corrupted or unreadable
- **LLM Parsing Failure**: Falls back to error status
- **File Size Limit**: Rejects files over 10MB (configurable)
- **Invalid JSON**: Handles malformed LLM responses
- **API Errors**: Graceful handling of LLM API failures

## LLM Processing Strategy

The service uses direct PDF document understanding:

1. **PDF Reading**: Converts PDF to base64 for LLM processing
2. **System Prompt**: Defines the assistant role and extraction rules
3. **Document Analysis**: LLM reads and analyzes the PDF directly

Key features:
- Temperature set to 0.0 for consistent extraction
- Max tokens limited to 512 for efficiency
- JSON output for structured data
- Conservative extraction when amounts are ambiguous
- No OCR preprocessing required

## Performance Considerations

- **PDF Processing**: ~2-5 seconds per file (LLM processing time)
- **Batch Processing**: Files processed sequentially
- **Memory**: ~50-100MB per concurrent request
- **API Costs**: Depends on LLM provider pricing

## Troubleshooting

### LLM API errors

- Check API key is valid
- Verify API quota/credits
- Check network connectivity
- Review logs for specific error messages

## Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest
```

### Code Formatting

```bash
# Install formatters
pip install black isort

# Format code
black app/
isort app/
```

## License

MIT License

## Support

For issues or questions, please open an issue on the repository.
