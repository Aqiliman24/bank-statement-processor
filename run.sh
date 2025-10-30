#!/bin/bash

# Bank Statement Processor - Run Script

echo "Starting Bank Statement Processor..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found. Please copy .env.example to .env and configure."
    exit 1
fi

# Create uploads directory
mkdir -p uploads

# Run the application
echo "Starting server on http://localhost:8000"
echo "API docs available at http://localhost:8000/docs"
python main.py
