FROM python:3.11-slim

WORKDIR /workspace

# System deps (minimal for cloud)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install cloud-optimized dependencies (no easyocr/llama/playwright)
COPY requirements-cloud.txt ./nexus/requirements-cloud.txt
RUN pip install --no-cache-dir -r ./nexus/requirements-cloud.txt

# Copy application code
COPY . ./nexus/

# Data directory
RUN mkdir -p /workspace/nexus/data/uploads

ENV PYTHONPATH=/workspace

# Cloud Run injects PORT (default 8080)
ENV PORT=8080
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/status')" || exit 1

CMD ["sh", "-c", "python -m uvicorn nexus.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
