import os
import threading
import time
from collections import Counter
from datetime import datetime
import psutil
from src.utils.logger import get_logger
from src.utils.metrics import get_runtime_stats

logger = get_logger("jarvis.monitor")

_MONITOR_LOCK = threading.Lock()
_STOP_EVENT = threading.Event()
_MONITOR_THREAD: threading.Thread | None = None

_SESSION = {
    "status": "idle",  # idle | running | completed | stopped
    "started_at": None,
    "finished_at": None,
    "duration_minutes": 0,
    "interval_seconds": 5,
    "samples": [],
    "top_ram_processes": Counter(),
    "high_ram_alerts": 0,
}


def _sample_top_ram_processes(limit: int = 3) -> list[tuple[str, float]]:
    procs = []
    for proc in psutil.process_iter(["name", "memory_info"]):
        try:
            info = proc.info
            mem_info = info.get("memory_info")
            if mem_info:
                mb = mem_info.rss / (1024 ** 2)
                procs.append((info.get("name") or "desconhecido", mb))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    procs.sort(key=lambda item: item[1], reverse=True)
    return procs[:limit]


def _monitor_worker(duration_minutes: int, interval_seconds: int) -> None:
    end_time = time.time() + (duration_minutes * 60)
    logger.info("Monitoramento em background iniciado (duracao=%d min, intervalo=%ds)", duration_minutes, interval_seconds)

    while not _STOP_EVENT.is_set() and time.time() < end_time:
        cpu = psutil.cpu_percent(interval=0.2)
        ram = psutil.virtual_memory()
        ram_used_gb = round(ram.used / (1024 ** 3), 2)
        top_procs = _sample_top_ram_processes(limit=3)

        with _MONITOR_LOCK:
            _SESSION["samples"].append(
                {
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "cpu_percent": cpu,
                    "ram_percent": ram.percent,
                    "ram_used_gb": ram_used_gb,
                }
            )
            for name, mb in top_procs:
                if mb > _SESSION["top_ram_processes"][name]:
                    _SESSION["top_ram_processes"][name] = round(mb, 1)

            if ram.percent >= 90.0:
                _SESSION["high_ram_alerts"] += 1
                logger.warning("Alerta proativo: RAM do sistema atingiu %.1f%% (%.2f GB)", ram.percent, ram_used_gb)

        remaining = end_time - time.time()
        if remaining <= 0:
            break
        _STOP_EVENT.wait(timeout=min(interval_seconds, remaining))

    with _MONITOR_LOCK:
        _SESSION["status"] = "stopped" if _STOP_EVENT.is_set() else "completed"
        _SESSION["finished_at"] = datetime.now().strftime("%H:%M:%S")
        total_samples = len(_SESSION["samples"])

    logger.info("Monitoramento em background finalizado (status=%s, amostras=%d)", _SESSION["status"], total_samples)
    if not _STOP_EVENT.is_set():
        print(f"\n  [MONITOR -> CONCLUÍDO]: Coleta de {duration_minutes} min finalizada ({total_samples} amostras). Peça o relatório quando quiser.")


def start_background_monitor(duration_minutes: int = 5, interval_seconds: int = 5) -> dict:
    """Inicia o monitoramento autônomo de CPU, RAM e processos em segundo plano sem travar o assistente.

    Args:
        duration_minutes: Duração total do monitoramento em minutos (entre 1 e 30; padrão 5).
        interval_seconds: Intervalo entre coletas em segundos (entre 2 e 60; padrão 5).
    """
    global _MONITOR_THREAD

    safe_duration = max(1, min(30, int(duration_minutes)))
    safe_interval = max(2, min(60, int(interval_seconds)))

    with _MONITOR_LOCK:
        if _MONITOR_THREAD and _MONITOR_THREAD.is_alive():
            return {
                "status": "already_running",
                "message": "Já existe uma sessão de monitoramento ativa em segundo plano.",
                "samples_collected_so_far": len(_SESSION["samples"]),
                "duration_minutes": _SESSION["duration_minutes"],
            }

        _STOP_EVENT.clear()
        _SESSION["status"] = "running"
        _SESSION["started_at"] = datetime.now().strftime("%H:%M:%S")
        _SESSION["finished_at"] = None
        _SESSION["duration_minutes"] = safe_duration
        _SESSION["interval_seconds"] = safe_interval
        _SESSION["samples"] = []
        _SESSION["top_ram_processes"] = Counter()
        _SESSION["high_ram_alerts"] = 0

        _MONITOR_THREAD = threading.Thread(
            target=_monitor_worker,
            args=(safe_duration, safe_interval),
            daemon=True,
        )
        _MONITOR_THREAD.start()

    return {
        "status": "started",
        "duration_minutes": safe_duration,
        "interval_seconds": safe_interval,
        "message": f"Monitoramento autônomo iniciado em segundo plano por {safe_duration} minuto(s), amostrando a cada {safe_interval} segundos.",
    }


def get_monitoring_report() -> dict:
    """Retorna o relatório consolidado (médias, picos, quedas, processos ofensores e recomendações) do monitoramento."""
    with _MONITOR_LOCK:
        status = _SESSION["status"]
        samples = list(_SESSION["samples"])
        top_procs = _SESSION["top_ram_processes"].most_common(5)
        alerts = _SESSION["high_ram_alerts"]
        started_at = _SESSION["started_at"]
        finished_at = _SESSION["finished_at"]
        duration_minutes = _SESSION["duration_minutes"]

    if not samples:
        return {
            "status": status,
            "message": "Nenhuma amostra coletada ainda. Solicite o início do monitoramento primeiro.",
        }

    cpu_vals = [s["cpu_percent"] for s in samples]
    ram_vals = [s["ram_percent"] for s in samples]
    ram_gb_vals = [s["ram_used_gb"] for s in samples]

    cpu_avg = round(sum(cpu_vals) / len(cpu_vals), 1)
    cpu_peak = max(cpu_vals)
    cpu_min = min(cpu_vals)

    ram_avg = round(sum(ram_vals) / len(ram_vals), 1)
    ram_peak = max(ram_vals)
    ram_min = min(ram_vals)
    ram_peak_gb = max(ram_gb_vals)

    recommendations = []
    if ram_peak >= 85.0:
        recommendations.append("Uso de RAM elevado detectado; feche abas inativas do navegador ou apps em segundo plano.")
    if cpu_peak >= 80.0:
        recommendations.append("Picos intensos de CPU observados; verifique processos pesados rodando simultaneamente.")
    if not recommendations:
        recommendations.append("Sistema operando dentro de margens saudáveis durante a janela analisada.")

    return {
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "target_duration_minutes": duration_minutes,
        "samples_collected": len(samples),
        "cpu_stats": {"avg_percent": cpu_avg, "peak_percent": cpu_peak, "min_percent": cpu_min},
        "ram_stats": {
            "avg_percent": ram_avg,
            "peak_percent": ram_peak,
            "min_percent": ram_min,
            "peak_used_gb": ram_peak_gb,
        },
        "high_ram_alerts_count": alerts,
        "top_ram_consumers_mb": [{"process": name, "peak_mb": mb} for name, mb in top_procs],
        "recommendations": recommendations,
    }


def get_jarvis_health() -> dict:
    """Coleta a telemetria interna de saúde operacional do próprio J.A.R.V.I.S. (RAM, CPU, latência e provedores)."""
    proc = psutil.Process(os.getpid())
    mem_mb = round(proc.memory_info().rss / (1024 ** 2), 1)
    total_sys_mb = psutil.virtual_memory().total / (1024 ** 2)
    mem_share_percent = round((mem_mb / total_sys_mb) * 100, 2)
    proc_cpu = proc.cpu_percent(interval=0.2)
    threads_count = proc.num_threads()

    runtime = get_runtime_stats()

    with _MONITOR_LOCK:
        bg_monitor_status = _SESSION["status"]

    return {
        "status": "healthy",
        "process_ram_mb": mem_mb,
        "system_ram_share_percent": mem_share_percent,
        "process_cpu_percent": proc_cpu,
        "active_threads": threads_count,
        "background_monitor_status": bg_monitor_status,
        "llm_runtime": runtime,
    }


def stop_background_monitor() -> None:
    """Interrompe com segurança qualquer thread de monitoramento ativa ao encerrar o sistema."""
    _STOP_EVENT.set()
