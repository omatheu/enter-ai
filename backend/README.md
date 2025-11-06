# Backend MVP Guide

This directory contains the Phase 1 MVP for the document extraction service described in `docs/plano-dev-backend.md`.

## 1. Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # optional if you need a template
```

> The repository already includes `backend/.env` with `OPENAI_API_KEY`. Activate the virtual environment before starting the API to ensure dependencies are available.

## 2. Running the API

```bash
uvicorn main:app --reload --port 8001
```

Upload a PDF with a schema JSON payload using the `/extract` endpoint (e.g. with `curl` or `httpie`).

## 3. Example Invocation

```bash
http --form POST :8001/extract \
  label=carteira_oab \
  extraction_schema='{"nome": "Nome do profissional"}' \
  pdf_file@../docs/files/oab_1.pdf
```

## 4. Tests

Run automated checks with:

```bash
pytest
```

The suite includes:
- `tests/test_pdf_extractor.py`: validates raw PDF parsing.
- `tests/test_service_with_stub.py`: exercises the orchestration flow with a stubbed LLM.

## 5. Manual LLM Test

To perform an end-to-end run against OpenAI:

1. Confirm `OPENAI_API_KEY` is present in `.env` or the shell.
2. Use the example request above or adapt `scripts/run_example.py` (provided below).

```bash
python scripts/run_example.py
```

The script loads the first record from `docs/data/dataset.json` and prints the formatted extraction response.
