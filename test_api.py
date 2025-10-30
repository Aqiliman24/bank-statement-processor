"""
Example script to test the Bank Statement Processor API.
"""

import requests
import json
from pathlib import Path


def test_health_check():
    """Test the health check endpoint."""
    print("Testing health check...")
    response = requests.get("http://localhost:8000/api/v1/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")


def test_process_single(pdf_path: str):
    """Test processing a single PDF file."""
    print(f"Testing single file processing: {pdf_path}")
    
    if not Path(pdf_path).exists():
        print(f"Error: File not found: {pdf_path}\n")
        return
    
    with open(pdf_path, 'rb') as f:
        files = {'file': (Path(pdf_path).name, f, 'application/pdf')}
        response = requests.post(
            "http://localhost:8000/api/v1/process-single",
            files=files
        )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")


def test_process_batch(pdf_paths: list):
    """Test processing multiple PDF files."""
    print(f"Testing batch processing: {len(pdf_paths)} files")
    
    files = []
    for pdf_path in pdf_paths:
        if Path(pdf_path).exists():
            files.append(
                ('files', (Path(pdf_path).name, open(pdf_path, 'rb'), 'application/pdf'))
            )
        else:
            print(f"Warning: File not found: {pdf_path}")
    
    if not files:
        print("Error: No valid files to process\n")
        return
    
    try:
        response = requests.post(
            "http://localhost:8000/api/v1/process",
            files=files
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    finally:
        # Close all file handles
        for _, (_, file_obj, _) in files:
            file_obj.close()


def main():
    """Run API tests."""
    print("=" * 60)
    print("Bank Statement Processor API Tests")
    print("=" * 60 + "\n")
    
    # Test health check
    test_health_check()
    
    # Example: Test with your PDF files
    # Uncomment and modify paths as needed
    
    # test_process_single("path/to/your/statement.pdf")
    
    # test_process_batch([
    #     "path/to/statement1.pdf",
    #     "path/to/statement2.pdf",
    #     "path/to/statement3.pdf"
    # ])
    
    print("=" * 60)
    print("Tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
