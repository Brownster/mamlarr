import pytest
from aiohttp import ClientSession, web

from mamlarr_service.providers.qbit import CapabilityProbeError, QbitCapabilities


@pytest.mark.asyncio
async def test_capabilities_probe_prefers_webapi(aiohttp_server):
    async def webapi(request):
        return web.Response(text="2.10.3")

    app = web.Application()
    app.router.add_get("/api/v2/app/webapiVersion", webapi)

    server = await aiohttp_server(app)
    async with ClientSession() as session:
        caps = await QbitCapabilities.probe(session, str(server.make_url("")))
    assert caps.api_major == 2
    assert caps.supports("/api/v2/app/webapiVersion")
    assert caps.prefers_v2()


@pytest.mark.asyncio
async def test_capabilities_probe_falls_back_to_legacy(aiohttp_server):
    async def webapi(request):
        return web.Response(status=404)

    async def app_version(request):
        return web.Response(status=404)

    async def legacy(request):
        return web.Response(text="1.0")

    app = web.Application()
    app.router.add_get("/api/v2/app/webapiVersion", webapi)
    app.router.add_get("/api/v2/app/version", app_version)
    app.router.add_get("/version/api", legacy)

    server = await aiohttp_server(app)
    async with ClientSession() as session:
        caps = await QbitCapabilities.probe(session, str(server.make_url("")))
    assert caps.api_major == 1
    assert caps.supports("/version/api")
    assert not caps.prefers_v2()


@pytest.mark.asyncio
async def test_capabilities_probe_requires_version(aiohttp_server):
    async def webapi(request):
        return web.Response(status=404)

    app = web.Application()
    app.router.add_get("/api/v2/app/webapiVersion", webapi)

    server = await aiohttp_server(app)
    async with ClientSession() as session:
        with pytest.raises(CapabilityProbeError):
            await QbitCapabilities.probe(session, str(server.make_url("")))
