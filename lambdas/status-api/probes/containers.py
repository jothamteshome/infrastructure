import asyncio
import aioboto3

INSTANCE_ID = "i-0ba2a719db973d795"
REGION      = "us-east-1"

EXCLUDED_CONTAINERS = {"db-init"}

# How long to wait for the SSM command to complete before giving up
SSM_POLL_INTERVAL_S = 1
SSM_MAX_POLLS       = 15

DOCKER_STATS_CMD = (
    "docker stats --no-stream --format "
    "'{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}'"
)


async def get_container_stats() -> dict:
    """
    Fetches per-container CPU and memory stats from the EC2 instance
    via SSM Run Command. Read-only — does not affect running containers.
    Falls back gracefully if SSM fails for any reason.
    """
    session = aioboto3.Session()
    try:
        async with session.client("ssm", region_name=REGION) as ssm:
            resp = await ssm.send_command(
                InstanceIds=[INSTANCE_ID],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": [DOCKER_STATS_CMD]},
            )
            command_id = resp["Command"]["CommandId"]

            result = await _poll_command(ssm, command_id)

        if result["Status"] != "Success":
            return {"error": f"SSM command status: {result['Status']}"}

        return _parse_stats_output(result["StandardOutputContent"])

    except Exception as e:
        return {"error": str(e)}


async def _poll_command(ssm, command_id: str) -> dict:
    for _ in range(SSM_MAX_POLLS):
        await asyncio.sleep(SSM_POLL_INTERVAL_S)
        result = await ssm.get_command_invocation(
            CommandId=command_id,
            InstanceId=INSTANCE_ID,
        )
        if result["Status"] in ("Success", "Failed", "Cancelled", "TimedOut"):
            return result
    return {"Status": "TimedOut", "StandardOutputContent": ""}


def _parse_stats_output(raw: str) -> dict:
    stats = {}
    for line in raw.strip().splitlines():
        parts = line.split("|")
        if len(parts) != 4:
            continue

        name, cpu, mem_usage, mem_perc = parts
        name = name.strip()

        if name in EXCLUDED_CONTAINERS:
            continue

        mem_parts = mem_usage.split(" / ")
        stats[name] = {
            "cpu_percent":    cpu.strip().rstrip("%"),
            "memory_usage":   mem_parts[0].strip() if len(mem_parts) == 2 else mem_usage.strip(),
            "memory_limit":   mem_parts[1].strip() if len(mem_parts) == 2 else None,
            "memory_percent": mem_perc.strip().rstrip("%"),
        }

    return stats