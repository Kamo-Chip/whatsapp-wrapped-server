# WhatsApp Wrapped API

Small FastAPI service that analyzes an exported WhatsApp chat text file and returns "wrapped" statistics (top talkers, busiest hour, most used words/emojis, etc.). This repository contains a single service implementation in `server.py`.

## Contents

- `server.py` - FastAPI application exposing a single POST endpoint `/wrapped` that accepts a WhatsApp-exported `.txt` file and returns JSON statistics.
- `requirements.txt` - Python dependencies used by the project (install with pip).

## Prerequisites

- Python 3.11+ (3.10 may work; code was developed on Python 3.13-compatible runtime). Use your system Python or create a virtual environment.

## Setup (recommended)

1. Create and activate a virtual environment (zsh example):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

If `requirements.txt` is missing or you prefer, install the essentials manually:

```bash
pip install fastapi uvicorn pydantic
```

## Run (development)

Start the server with `uvicorn` pointing at the `app` in `server.py`:

```bash
# from project root
uvicorn server:app --reload --host 127.0.0.1 --port 8000
```

The API will be available at `http://127.0.0.1:8000` and the automatic docs at `http://127.0.0.1:8000/docs`.

## Endpoint

- POST `/wrapped` — accepts a form file upload (field name `file`) containing the WhatsApp exported `.txt` chat file. Returns a JSON response with analysis statistics.

Important behaviors and constraints:
- Only `.txt` uploads are accepted.
- Maximum file size: 5 MB (server returns 413 if larger).
- The server attempts to decode as UTF-8, then UTF-16; if both fail it returns a 400 error.
- The current implementation filters messages to year 2025 only (see `server.py`). If you want a different year range, update `compute_stats`.

## Example: using curl to test

Replace `chat.txt` with your exported WhatsApp `.txt` file.

```bash
curl -X POST "http://127.0.0.1:8000/wrapped" \
  -F "file=@chat.txt;type=text/plain" \
  -H "Accept: application/json"
```

You should receive a JSON payload matching the `WrappedResponse` model defined in `server.py`.

## Notes & troubleshooting

- If you receive `No WhatsApp messages detected`, verify you uploaded the raw exported chat `.txt` and that lines match the expected header format (e.g. `[YYYY/MM/DD, HH:MM:SS] Sender: message`).
- If messages include non-UTF-8 characters, re-export the chat using WhatsApp's export options or open/save the file with UTF-8 encoding.
- The service recognizes common media placeholders (e.g. `<Media omitted>`) and excludes those from word/emoji statistics.
