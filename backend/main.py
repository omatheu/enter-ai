"""FastAPI entrypoint for Phase 1 MVP."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.models import ExtractionRequest
from app.services.extraction import ExtractionService

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
LOGGER = logging.getLogger(__name__)

app = FastAPI(title="Enter AI Extraction API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = ExtractionService()


def _write_temp_pdf(upload: UploadFile) -> Path:
    suffix = Path(upload.filename or "uploaded.pdf").suffix or ".pdf"
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        contents = upload.file.read()
        temp_file.write(contents)
        temp_file.flush()
    finally:
        temp_file.close()
    LOGGER.debug("Temporary PDF stored at %s", temp_file.name)
    return Path(temp_file.name)


@app.post("/extract")
async def extract(
    label: str = Form(...),
    extraction_schema: str = Form(...),
    pdf_file: UploadFile = File(...),
):
    """Extract structured data from the uploaded PDF according to ``extraction_schema``."""

    try:
        schema: Dict[str, str] = json.loads(extraction_schema)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid schema JSON: {exc}") from exc

    temp_pdf_path: Path | None = None
    try:
        temp_pdf_path = _write_temp_pdf(pdf_file)
        request = ExtractionRequest(label=label, schema=schema, pdf_path=str(temp_pdf_path))
        result = await service.extract(request)
        return JSONResponse(content=result.model_dump(by_alias=True, mode='json'))
    finally:
        if temp_pdf_path and temp_pdf_path.exists():
            temp_pdf_path.unlink(missing_ok=True)


@app.get("/health")
async def healthcheck() -> Dict[str, Any]:
    """Simple health endpoint useful during development."""

    return {"status": "ok"}
