FROM python:3.12-slim

# Put code at /workspace/nexus/ so 'nexus' is importable as a package
WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt ./nexus/requirements.txt
RUN pip install --no-cache-dir -r ./nexus/requirements.txt

# Copy application code into /workspace/nexus/
COPY . ./nexus/

# Create data directory
RUN mkdir -p /workspace/nexus/data

# PYTHONPATH so 'import nexus' works
ENV PYTHONPATH=/workspace

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/')" || exit 1

# Run via uvicorn
CMD ["python", "-m", "uvicorn", "nexus.main:app", "--host", "0.0.0.0", "--port", "8000"]
