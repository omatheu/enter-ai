"""Utility script to exercise the extraction service with a local dataset entry."""

import asyncio
import json
import sys
from pathlib import Path

# Add backend directory to Python path
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.models import ExtractionRequest
from app.services.extraction import ExtractionService

# Project root directory
BASE_DIR = Path(__file__).resolve().parents[2]
DATASET_PATH = BASE_DIR / "docs" / "data" / "dataset.json"
FILES_DIR = BASE_DIR / "docs" / "files"


async def run() -> None:
    dataset = json.loads(DATASET_PATH.read_text())
    record = dataset[0]
    pdf_path = FILES_DIR / record["pdf_path"]

    request = ExtractionRequest(
        label=record["label"],
        schema=record["extraction_schema"],
        pdf_path=str(pdf_path),
    )

    service = ExtractionService()
    result = await service.extract(request)
    print(result.model_dump_json(indent=2, by_alias=True))


if __name__ == "__main__":
    asyncio.run(run())
