import httpx

limits = httpx.Limits(max_keepalive_connections=20, max_connections=40)
timeout = httpx.Timeout(connect=2.0, read=6.0, write=6.0, pool=2.0)

async_client = httpx.AsyncClient(limits=limits, timeout=timeout, http2=False)  # HTTP/1.1 oftast stabilare i dev

async def aget(url: str, headers: dict | None = None, params: dict | None = None):
    r = await async_client.get(url, headers=headers, params=params)
    r.raise_for_status()
    return r

async def apost(url: str, headers: dict | None = None, json: dict | None = None):
    r = await async_client.post(url, headers=headers, json=json)
    r.raise_for_status()
    return r
