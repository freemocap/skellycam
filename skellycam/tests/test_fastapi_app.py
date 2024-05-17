import pytest
from httpx import AsyncClient

from skellycam.api.app_factory import create_app


@pytest.mark.asyncio
async def test_app() -> None:
    app = create_app()

    # note: you _must_ set `base_url` for relative urls like "/" to work
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        r = await client.get("/")
        assert r.status_code == 307 #redirect
