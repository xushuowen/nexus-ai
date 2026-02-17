"""Launcher script - run from inside the nexus/ directory."""
import sys
from pathlib import Path

# Add parent directory to path so 'nexus' package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn
from nexus import config

if __name__ == "__main__":
    host = config.get("app.host", "0.0.0.0")
    port = config.get("app.port", 8000)
    print(f"\n  Starting Nexus AI on http://{host}:{port}\n")
    uvicorn.run("nexus.main:app", host=host, port=port, reload=False)
