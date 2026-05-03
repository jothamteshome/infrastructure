import asyncio
import aiohttp

STATIC_SITES = [
    ("snake-game",   "https://snake-game.whymighta.net"),
    ("pixel-sorter", "https://pixel-sorter.whymighta.net"),
]

WATCH_TOGETHER_FRONTEND_URL            = "https://watch-together.whymighta.net"
WATCH_TOGETHER_BACKEND_HEALTH_ENDPOINT = "https://api.watch-together.whymighta.net/health"


async def check_http(session: aiohttp.ClientSession, url: str) -> dict:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            return {"online": resp.status < 500, "status_code": resp.status}
    except Exception as e:
        return {"online": False, "error": str(e)}


async def check_all_sites() -> dict:
    async with aiohttp.ClientSession() as session:
        all_urls = (
            [url for _, url in STATIC_SITES]
            + [WATCH_TOGETHER_FRONTEND_URL, WATCH_TOGETHER_BACKEND_HEALTH_ENDPOINT]
        )
        results = await asyncio.gather(*[check_http(session, url) for url in all_urls])

    n = len(STATIC_SITES)
    sites = {
        name: {"url": url, **results[i]}
        for i, (name, url) in enumerate(STATIC_SITES)
    }
    sites["watch-together"] = {
        "frontend": {"url": WATCH_TOGETHER_FRONTEND_URL,            **results[n]},
        "backend":  {"url": WATCH_TOGETHER_BACKEND_HEALTH_ENDPOINT, **results[n + 1]},
    }
    return sites