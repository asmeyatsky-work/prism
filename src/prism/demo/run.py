"""
Run the PRISM demo server.

Starts the FastAPI application with Uvicorn, seeding the catalogue
with luxury product data on startup. The interactive API documentation
is available at http://localhost:8000/docs.

Usage:
    python -m prism.demo.run
    # or
    python src/prism/demo/run.py
"""

import uvicorn

from prism.demo.api.app import create_app

if __name__ == "__main__":
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
