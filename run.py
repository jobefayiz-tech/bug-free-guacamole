"""Production entry point (works on Windows, Linux and macOS).

    python run.py            # listens on 0.0.0.0:8000
    PORT=9000 python run.py
"""
import os

from waitress import serve

from app import create_app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"Listening on http://0.0.0.0:{port}")
    serve(create_app(), host="0.0.0.0", port=port, threads=8, max_request_body_size=64 * 1024 * 1024)
