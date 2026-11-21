import os
import platform
from datetime import datetime
import psutil


def get_system_telemetry() -> dict:
    """Coleta métricas em tempo real de CPU, memória RAM, disco, tempo de atividade e data/hora local."""
    cpu_percent = psutil.cpu_percent(interval=0.5)
    cpu_cores = psutil.cpu_count(logical=True)

    ram = psutil.virtual_memory()
    ram_used_gb = round(ram.used / (1024 ** 3), 2)
    ram_total_gb = round(ram.total / (1024 ** 3), 2)

    root_drive = os.path.abspath(os.sep)
    disk = psutil.disk_usage(root_drive)
    disk_used_gb = round(disk.used / (1024 ** 3), 1)
    disk_total_gb = round(disk.total / (1024 ** 3), 1)

    boot_timestamp = psutil.boot_time()
    uptime_seconds = int(datetime.now().timestamp() - boot_timestamp)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    return {
        "status": "ok",
        "datetime": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "os": f"{platform.system()} {platform.release()}",
        "cpu_usage_percent": cpu_percent,
        "cpu_logical_cores": cpu_cores,
        "ram_usage_percent": ram.percent,
        "ram_used_gb": ram_used_gb,
        "ram_total_gb": ram_total_gb,
        "disk_usage_percent": disk.percent,
        "disk_used_gb": disk_used_gb,
        "disk_total_gb": disk_total_gb,
        "uptime": f"{hours}h {minutes}m",
    }
