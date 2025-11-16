import asyncio
import pytest
from aiohttp import ClientSession, web

from mamlarr_service.qbit_client import QbitClient


@pytest.mark.asyncio
async def test_qbit_client_happy_path(aiohttp_server):
    torrent_files = []

    async def login(request):
        data = await request.post()
        assert data["username"] == "user"
        assert data["password"] == "pass"
        return web.Response(text="Ok.")

    async def version(request):
        return web.Response(text="v2.0.0")

    async def add(request):
        torrent_files.append(await request.read())
        return web.Response(text="Ok.")

    async def info(request):
        return web.json_response(
            [
                {
                    "hash": "ABC123",
                    "total_size": 200,
                    "downloaded": 100,
                    "save_path": "/downloads",
                    "name": "book",
                    "state": "uploading",
                }
            ]
        )

    async def files(request):
        return web.json_response([{"name": "book.mp3"}])

    async def delete(request):
        data = await request.post()
        assert data["hashes"] == "ABC123"
        return web.Response(text="Ok.")

    app = web.Application()
    app.router.add_post("/api/v2/auth/login", login)
    app.router.add_get("/api/v2/app/version", version)
    app.router.add_post("/api/v2/torrents/add", add)
    app.router.add_get("/api/v2/torrents/info", info)
    app.router.add_get("/api/v2/torrents/files", files)
    app.router.add_post("/api/v2/torrents/delete", delete)

    server = await aiohttp_server(app)
    async with ClientSession(cookie_jar=web.CookieJar()) as session:
        client = QbitClient(
            session,
            str(server.make_url("")),
            "user",
            "pass",
        )
        await client.test_connection()
        await client.add_torrent(b"dummy")
        torrents = await client.list_torrents(["ABC123"])
        assert len(torrents) == 1
        assert torrents[0]["hash"] == "ABC123"
        files_resp = await client.list_files("ABC123")
        assert files_resp[0]["name"] == "book.mp3"
        await client.remove_torrent("ABC123")

    assert torrent_files, "torrent upload should have been called"
