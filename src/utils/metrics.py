import threading
import time
from datetime import datetime

_LOCK = threading.Lock()
_START_TIME = time.time()
_STATS = {
    "active_provider": "N/A",
    "active_model": "N/A",
    "total_calls": 0,
    "failover_count": 0,
    "error_count": 0,
    "latencies_ms": [],
}


def set_initial_provider(provider: str, model: str) -> None:
    with _LOCK:
        _STATS["active_provider"] = provider
        _STATS["active_model"] = model


def record_llm_call(
    provider: str,
    model: str,
    latency_ms: float,
    used_fallback: bool = False,
    failed: bool = False,
) -> None:
    with _LOCK:
        _STATS["active_provider"] = provider
        _STATS["active_model"] = model
        _STATS["total_calls"] += 1
        if used_fallback:
            _STATS["failover_count"] += 1
        if failed:
            _STATS["error_count"] += 1
        else:
            _STATS["latencies_ms"].append(round(latency_ms, 1))
            if len(_STATS["latencies_ms"]) > 50:
                _STATS["latencies_ms"].pop(0)


def get_runtime_stats() -> dict:
    with _LOCK:
        latencies = _STATS["latencies_ms"]
        avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else 0.0
        last_latency = latencies[-1] if latencies else 0.0
        uptime_sec = int(time.time() - _START_TIME)
        hours, rem = divmod(uptime_sec, 3600)
        minutes, seconds = divmod(rem, 60)

        return {
            "started_at": datetime.fromtimestamp(_START_TIME).strftime("%d/%m/%Y %H:%M:%S"),
            "session_uptime": f"{hours}h {minutes}m {seconds}s",
            "active_provider": _STATS["active_provider"],
            "active_model": _STATS["active_model"],
            "total_llm_calls": _STATS["total_calls"],
            "failover_count": _STATS["failover_count"],
            "error_count": _STATS["error_count"],
            "avg_latency_ms": avg_latency,
            "last_latency_ms": last_latency,
        }
