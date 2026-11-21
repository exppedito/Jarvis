import json
import shutil
import subprocess
import webbrowser
from pathlib import Path


def _load_permissions() -> dict:
    """Carrega a lista de aplicativos autorizados de config/permissions.json."""
    root_dir = Path(__file__).resolve().parents[2]
    perm_path = root_dir / "config" / "permissions.json"

    if not perm_path.exists():
        raise FileNotFoundError(f"Arquivo de permissões não encontrado em: {perm_path}")

    with open(perm_path, "r", encoding="utf-8") as file:
        return json.load(file).get("allowed_apps", {})


def list_allowed_applications() -> dict:
    """Lista todos os aplicativos e links que o J.A.R.V.I.S. tem permissão para abrir."""
    allowed = _load_permissions()
    summary = {key: info.get("description", key) for key, info in allowed.items()}
    return {"status": "ok", "allowed_applications": summary}


def open_application(app_name: str) -> dict:
    """Abre um aplicativo ou link autorizado na whitelist (config/permissions.json).

    Args:
        app_name: Nome identificador do aplicativo (ex: 'vscode', 'calculadora', 'bloco_de_notas', 'explorador', 'github', 'youtube', 'navegador').
    """
    allowed = _load_permissions()
    normalized = app_name.lower().strip().replace(" ", "_")

    if normalized not in allowed:
        permitted_list = [f"{k} ({v.get('description', k)})" for k, v in allowed.items()]
        return {
            "status": "denied",
            "requested_app": app_name,
            "reason": "Aplicativo ausente da whitelist de segurança (config/permissions.json).",
            "permitted_applications": permitted_list,
            "instruction": "Informe ao usuário que este aplicativo não está autorizado e cite os aplicativos permitidos.",
        }

    entry = allowed[normalized]
    target = entry["command"]
    entry_type = entry.get("type", "app")

    try:
        if entry_type == "url":
            webbrowser.open(target)
            return {"status": "launched", "app": normalized, "target": target}

        resolved_bin = shutil.which(target) or target
        subprocess.Popen([resolved_bin], shell=False)
        return {"status": "launched", "app": normalized, "target": resolved_bin}

    except Exception as e:
        return {"status": "error", "app": normalized, "details": str(e)}
