# Base image with Python and pip
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy application code and dependency list
COPY cleaner.py .
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port for /health endpoint
EXPOSE 8000

# Run the cleaner
CMD ["python", "cleaner.py"]
