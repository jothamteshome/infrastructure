import asyncio
import aiohttp

STATIC_SITES = [
    ("snake-game",     "https://snake-game.whymighta.net"),
    ("pixel-sorter",   "https://pixel-sorter.whymighta.net"),
    ("watch-together", "https://watch-together.whymighta.net"),
]

APIS = [
    ("watch-together", "https://api.watch-together.whymighta.net/health"),
]


async def check_http(session: aiohttp.ClientSession, url: str) -> dict:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            return {"online": resp.status < 500, "status_code": resp.status}
    except Exception as e:
        return {"online": False, "error": str(e)}


async def check_all_sites() -> dict:
    all_entries = STATIC_SITES + APIS
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(*[check_http(session, url) for _, url in all_entries])

    n = len(STATIC_SITES)
    sites = {
        name: {"url": url, **results[i]}
        for i, (name, url) in enumerate(STATIC_SITES)
    }
    apis = {
        name: {"url": url, **results[n + i]}
        for i, (name, url) in enumerate(APIS)
    }
    return {"sites": sites, "apis": apis}