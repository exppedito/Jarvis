from src.tools.system_info import get_system_telemetry
from src.tools.app_launcher import open_application, list_allowed_applications

# Lista de funções expostas ao modelo de linguagem
AVAILABLE_TOOLS = [
    get_system_telemetry,
    open_application,
    list_allowed_applications,
]

# Mapa rápido para invocação segura pelo nome
TOOL_EXECUTORS = {func.__name__: func for func in AVAILABLE_TOOLS}


def execute_tool(name: str, args: dict | None = None) -> dict:
    """Executa uma ferramenta registrada de forma isolada e retorna um dicionário estruturado."""
    if name not in TOOL_EXECUTORS:
        return {"status": "error", "details": f"Ferramenta '{name}' não registrada."}

    safe_args = args or {}
    try:
        return TOOL_EXECUTORS[name](**safe_args)
    except Exception as e:
        return {"status": "error", "details": f"Falha ao executar '{name}': {e}"}
