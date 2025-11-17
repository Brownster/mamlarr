import pytest
from aiohttp import ClientSession, CookieJar, web

from mamlarr_service.providers.qbit import (
    QbitAddOptions,
    QbitCapabilities,
    QbitClient,
    QueueingDisabledError,
)


TEST_CAPABILITIES = QbitCapabilities(
    api_major=2, supported_endpoints=frozenset({"/api/v2/app/webapiVersion"})
)


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
    async with ClientSession(cookie_jar=CookieJar()) as session:
        client = QbitClient(
            session,
            str(server.make_url("")),
            "user",
            "pass",
            TEST_CAPABILITIES,
        )
        await client.test_connection()
        await client.add_torrent(b"dummy", options=QbitAddOptions(category="books"))
        torrents = await client.list_torrents(["ABC123"])
        assert len(torrents) == 1
        assert torrents[0]["hash"] == "ABC123"
        files_resp = await client.list_files("ABC123")
        assert files_resp[0]["name"] == "book.mp3"
        await client.remove_torrent("ABC123")

    assert torrent_files, "torrent upload should have been called"


@pytest.mark.asyncio
async def test_qbit_client_reauth_on_forbidden(aiohttp_server):
    login_calls = 0
    info_attempts = 0

    async def login(request):
        nonlocal login_calls
        login_calls += 1
        return web.Response(text="Ok.")

    async def info(request):
        nonlocal info_attempts
        info_attempts += 1
        if info_attempts == 1:
            return web.Response(status=403)
        return web.json_response([{"hash": "ABC123"}])

    app = web.Application()
    app.router.add_post("/api/v2/auth/login", login)
    app.router.add_get("/api/v2/torrents/info", info)

    server = await aiohttp_server(app)
    async with ClientSession(cookie_jar=CookieJar()) as session:
        client = QbitClient(
            session,
            str(server.make_url("")),
            "user",
            "pass",
            TEST_CAPABILITIES,
        )
        torrents = await client.list_torrents(["ABC123"])
        assert torrents[0]["hash"] == "ABC123"
    assert login_calls == 2
    assert info_attempts == 2


@pytest.mark.asyncio
async def test_qbit_client_queueing_disabled_error(aiohttp_server):
    async def login(request):
        return web.Response(text="Ok.")

    async def add(request):
        return web.Response(status=409, text="Queueing is not enabled")

    app = web.Application()
    app.router.add_post("/api/v2/auth/login", login)
    app.router.add_post("/api/v2/torrents/add", add)

    server = await aiohttp_server(app)
    async with ClientSession(cookie_jar=CookieJar()) as session:
        client = QbitClient(
            session,
            str(server.make_url("")),
            "user",
            "pass",
            TEST_CAPABILITIES,
        )
        with pytest.raises(QueueingDisabledError):
            await client.add_torrent(b"data")
