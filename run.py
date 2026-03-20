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

    # Use HTTPS if SSL cert exists (required for PWA install on mobile)
    ssl_key  = Path(__file__).parent / "data" / "nexus.key"
    ssl_cert = Path(__file__).parent / "data" / "nexus.crt"
    if ssl_key.exists() and ssl_cert.exists():
        print(f"\n  Starting Nexus AI on https://{host}:{port}\n")
        uvicorn.run(
            "nexus.main:app", host=host, port=port, reload=False,
            ssl_keyfile=str(ssl_key), ssl_certfile=str(ssl_cert),
        )
    else:
        print(f"\n  Starting Nexus AI on http://{host}:{port}\n")
        uvicorn.run("nexus.main:app", host=host, port=port, reload=False)
