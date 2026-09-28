# Base Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Prevent Python from writing .pyc files and enable unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Apply schema migrations before starting the API process
COPY docker-entrypoint.sh /usr/local/bin/observa-entrypoint
RUN chmod +x /usr/local/bin/observa-entrypoint

# Expose FastAPI default port
EXPOSE 8000

# Command to run the API
ENTRYPOINT ["/usr/local/bin/observa-entrypoint"]
CMD ["uvicorn", "observa.app:app", "--host", "0.0.0.0", "--port", "8000"]
