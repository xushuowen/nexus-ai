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

# Google Cloud Run injects PORT (default 8080); fall back to 8080 locally
ENV PORT=8080
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/')" || exit 1

# Run via uvicorn — Cloud Run sets $PORT automatically
CMD ["sh", "-c", "python -m uvicorn nexus.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
