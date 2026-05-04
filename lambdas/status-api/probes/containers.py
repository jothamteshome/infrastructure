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
    "'{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}|{{.NetIO}}|{{.BlockIO}}'"
)

DOCKER_INSPECT_CMD = (
    "docker ps --format '{{.Names}}' | "
    "xargs docker inspect --format "
    "'{{.Name}}|{{.State.StartedAt}}|{{.RestartCount}}'"
)

DOCKER_PS_CMD = "docker ps -a --format '{{.Names}}|{{.Status}}'"

async def get_container_stats() -> dict:
    """
    Fetches per-container CPU and memory stats from the EC2 instance
    via SSM Run Command. Read-only — does not affect running containers.
    Falls back gracefully if SSM fails for any reason.
    """
    session = aioboto3.Session()
    try:
        async with session.client("ssm", region_name=REGION) as ssm:
            stats_id, inspect_id, ps_id = await asyncio.gather(
                _send_command(ssm, DOCKER_STATS_CMD),
                _send_command(ssm, DOCKER_INSPECT_CMD),
                _send_command(ssm, DOCKER_PS_CMD),
            )
            stats_out, inspect_out, ps_out = await asyncio.gather(
                _poll_command(ssm, stats_id),
                _poll_command(ssm, inspect_id),
                _poll_command(ssm, ps_id),
            )

        if stats_out["Status"] != "Success":
            return {"error": f"SSM stats status: {stats_out['Status']}"}

        containers = _parse_stats_output(stats_out["StandardOutputContent"])

        if inspect_out["Status"] == "Success":
            _merge_inspect(containers, inspect_out["StandardOutputContent"])

        if ps_out["Status"] == "Success":
            _merge_ps(containers, ps_out["StandardOutputContent"])

        return containers

    except Exception as e:
        return {"error": str(e)}
    

async def _send_command(ssm, command: str) -> str:
    resp = await ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [command]},
    )
    return resp["Command"]["CommandId"]


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
        if len(parts) != 6:
            continue

        name, cpu, mem_usage, mem_perc, net_io, block_io = parts
        name = name.strip()

        if name in EXCLUDED_CONTAINERS:
            continue

        mem_parts = mem_usage.split(" / ")
        net_parts = net_io.split(" / ")
        block_parts = block_io.split(" / ")

        stats[name] = {
            "cpu_percent":    cpu.strip().rstrip("%"),
            "memory_usage":   mem_parts[0].strip() if len(mem_parts) == 2 else mem_usage.strip(),
            "memory_limit":   mem_parts[1].strip() if len(mem_parts) == 2 else None,
            "memory_percent": mem_perc.strip().rstrip("%"),
            "net_in":         net_parts[0].strip() if len(net_parts) == 2 else net_io.strip(),
            "net_out":        net_parts[1].strip() if len(net_parts) == 2 else None,
            "block_read":     block_parts[0].strip() if len(block_parts) == 2 else block_io.strip(),
            "block_write":    block_parts[1].strip() if len(block_parts) == 2 else None,
        }

    return stats

def _merge_inspect(containers: dict, raw: str) -> None:
    for line in raw.strip().splitlines():
        parts = line.split("|")
        if len(parts) != 3:
            continue

        name, started_at, restart_count = parts
        name = name.strip().lstrip("/")

        if name not in containers:
            continue

        containers[name]["started_at"]     = started_at.strip()
        containers[name]["restart_count"]  = int(restart_count.strip())


def _merge_ps(containers: dict, raw: str) -> None:
    for line in raw.strip().splitlines():
        parts = line.split("|", 1)
        if len(parts) != 2:
            continue

        name, status = parts
        name = name.strip()

        if name in EXCLUDED_CONTAINERS or name in containers:
            continue

        containers[name] = {"online": False, "status": status.strip()}