from pathlib import Path
import yaml


def load_system_prompt() -> str:
    """Carrega e formata o system prompt a partir do arquivo config/personality.yaml."""
    # Navega de src/brain/prompt.py até a raiz do projeto
    root_dir = Path(__file__).resolve().parents[2]
    config_path = root_dir / "config" / "personality.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Arquivo de personalidade não encontrado em: {config_path}")

    with open(config_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    assistant_cfg = data.get("assistant", {})
    raw_prompt = data.get("system_prompt", "")

    user_title = assistant_cfg.get("user_title", "senhor")
    return raw_prompt.format(user_title=user_title).strip()
