#!/bin/bash
# Azure App Service startup script
# Fix: code is deployed to /home/site/wwwroot/ but imports expect a "nexus" package.
# Create a symlink so Python can resolve "from nexus import ..." correctly.

ln -sf /home/site/wwwroot /home/site/nexus
cd /home/site
export PYTHONPATH=/home/site:$PYTHONPATH

gunicorn --bind=0.0.0.0:8000 --timeout 600 --worker-class uvicorn.workers.UvicornWorker nexus.main:app
