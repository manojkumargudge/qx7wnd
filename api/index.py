"""Vercel Python function entry point.

Vercel serves this file at /api; vercel.json rewrites /api/(.*) here so every
API route reaches the FastAPI app, which sees the original /api/... path.
The app and the data it reads live in backend/ and data/processed/.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402,F401
