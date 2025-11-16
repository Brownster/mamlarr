from __future__ import annotations

import itertools
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

MOCK_DIR = Path(__file__).resolve().parent.parent / "mock_downloads"
MOCK_BOOK_DIR = MOCK_DIR / "mock_book"
MOCK_BOOK_DIR.mkdir(parents=True, exist_ok=True)
MOCK_FILE = MOCK_BOOK_DIR / "Part1.mp3"
if not MOCK_FILE.exists():
    MOCK_FILE.write_bytes(b"fake audio data")

app = FastAPI()
TORRENTS: Dict[str, Dict[str, Any]] = {}
COUNTER = itertools.count(1)


@app.get("/tor/js/loadSearchJSONbasic.php")
async def mock_search():
    data = [
        {
            "id": 1001,
            "title": "Mock Audiobook",
            "seeders": 5,
            "leechers": 0,
            "size": 123_456_789,
            "added": datetime.now(tz=timezone.utc).isoformat(),
            "tor_id": 1001,
        }
    ]
    return {"data": data}


@app.get("/torrents.php")
async def mock_torrent_file(id: int):
    # return minimal torrent bytes; content is irrelevant for the fake Transmission server
    return Response(content=b"mock-torrent-data", media_type="application/x-bittorrent")


@app.post("/transmission/rpc")
async def transmission_rpc(request: Request):
    payload = await request.json()
    method = payload.get("method")
    arguments = payload.get("arguments") or {}

    if method == "torrent-add":
        torrent_id = next(COUNTER)
        hash_string = f"mockhash{torrent_id}"
        torrent_info = {
            "id": torrent_id,
            "hashString": hash_string,
            "name": "mock_book",
            "downloadDir": str(MOCK_DIR),
            "leftUntilDone": 1,  # mark as downloading initially
            "status": 4,
            "files": [
                {"name": "mock_book/Part1.mp3"},
            ],
        }
        TORRENTS[hash_string] = torrent_info
        return JSONResponse(
            {
                "result": "success",
                "arguments": {"torrent-added": torrent_info},
            }
        )

    if method == "torrent-get":
        hashes = arguments.get("ids", [])
        torrents = []
        for hash_string in hashes:
            info = TORRENTS.get(hash_string)
            if not info:
                continue
            # Simulate download completion on first poll
            if info["leftUntilDone"] > 0:
                info["leftUntilDone"] = 0
                info["status"] = 6  # seeding
            torrents.append(info)
        return JSONResponse({"result": "success", "arguments": {"torrents": torrents}})

    if method == "torrent-remove":
        hashes = arguments.get("ids", [])
        for hash_string in hashes:
            TORRENTS.pop(hash_string, None)
        return JSONResponse({"result": "success", "arguments": {}})

    return JSONResponse(
        {"result": f"unknown-method-{method}", "arguments": {}}, status_code=400
    )
