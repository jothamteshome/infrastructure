import asyncio
import json
import time

from probes.minecraft import check_all_minecraft_servers
from probes.sites import check_all_sites
from probes.containers import get_container_stats

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "https://status.whymighta.net",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


async def main(event: dict) -> dict:
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return {"statusCode": 204, "headers": CORS_HEADERS, "body": ""}

    minecraft, sites, containers = await asyncio.gather(
        check_all_minecraft_servers(),
        check_all_sites(),
        get_container_stats(),
    )

    body = {
        "minecraft": minecraft,
        "sites": sites,
        "containers": containers,
        "checked_at": int(time.time()),
    }

    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps(body),
    }


def lambda_handler(event: dict, context) -> dict:
    return asyncio.run(main(event))