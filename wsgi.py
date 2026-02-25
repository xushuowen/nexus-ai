"""Production entry point for Google Cloud Run.

Google Cloud Run builds from the Dockerfile and starts the container via:
    CMD ["python", "-m", "uvicorn", "nexus.main:app", "--host", "0.0.0.0", "--port", "8080"]

This module is provided as an alternative entry point for gunicorn-based deployments:
    gunicorn --bind 0.0.0.0:$PORT --worker-class uvicorn.workers.UvicornWorker wsgi:app

Cloud Run automatically injects the PORT environment variable (default: 8080).
"""
from nexus.main import app  # noqa: F401

__all__ = ["app"]
