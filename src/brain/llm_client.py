import json
import os
import time
from google import genai
from google.genai import types
from groq import Groq
from src.brain.prompt import load_system_prompt
from src.tools.registry import AVAILABLE_TOOLS, execute_tool

GROQ_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_system_telemetry",
            "description": "Coleta métricas em tempo real de CPU, memória RAM, disco, tempo de atividade e data/hora local.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_application",
            "description": "Abre um aplicativo ou link autorizado na whitelist (config/permissions.json).",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Identificador do aplicativo (ex: 'vscode', 'calculadora', 'bloco_de_notas', 'explorador', 'github', 'youtube', 'navegador').",
                    }
                },
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_allowed_applications",
            "description": "Lista todos os aplicativos e links que o J.A.R.V.I.S. tem permissão para abrir.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


class JarvisBrain:
    """Gerencia a comunicação com o LLM, fallback de provedores, personalidade, memória e tool calling."""

    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "gemini").lower().strip()
        self.system_prompt = load_system_prompt()
        self.gemini_client = None
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
        self.gemini_history: list[types.Content] = []
        self.groq_client = None
        self.groq_model = ""
        self.groq_history: list[dict] = []

        self._initialize_provider()

    def _resolve_groq_model(self) -> str:
        """Descobre automaticamente um modelo de chat/tools ativo na conta Groq."""
        env_model = os.getenv("GROQ_MODEL", "").strip()
        if env_model:
            return env_model

        try:
            available = self.groq_client.models.list().data
            excluded = ("whisper", "tts", "orpheus", "guard", "safeguard", "embed")
            chat_models = [
                m.id
                for m in available
                if getattr(m, "active", True)
                and not any(kw in m.id.lower() for kw in excluded)
            ]

            preferred_prefixes = (
                "meta-llama/llama-4",
                "llama-4",
                "qwen/",
                "openai/gpt-oss",
                "llama-3.3",
                "llama-3.1",
            )
            for prefix in preferred_prefixes:
                for model_id in chat_models:
                    if model_id.lower().startswith(prefix):
                        return model_id

            if chat_models:
                return chat_models[0]
        except Exception:
            pass

        return "llama-3.1-8b-instant"

    def _initialize_provider(self) -> None:
        gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        groq_key = os.getenv("GROQ_API_KEY", "").strip()

        if gemini_key and gemini_key != "sua_chave_aqui":
            self.gemini_client = genai.Client(api_key=gemini_key)
            self.gemini_history = []

        if groq_key and groq_key != "sua_chave_opcional_aqui":
            self.groq_client = Groq(api_key=groq_key)
            self.groq_model = self._resolve_groq_model()
            self.groq_history = [{"role": "system", "content": self.system_prompt}]

        if self.provider == "gemini" and not self.gemini_client:
            raise ValueError("GEMINI_API_KEY não configurada corretamente no arquivo .env.")
        if self.provider == "groq" and not self.groq_client:
            raise ValueError("GROQ_API_KEY não configurada corretamente no arquivo .env.")
        if self.provider not in {"gemini", "groq"}:
            raise ValueError(f"Provedor '{self.provider}' não suportado. Use 'gemini' ou 'groq'.")

    def _call_with_retry(self, func, max_retries: int = 3):
        """Executa chamadas à API com backoff para falhas transitórias (ignora retry em cota diária esgotada)."""
        delay = 1.5
        for attempt in range(1, max_retries + 1):
            try:
                return func()
            except Exception as e:
                err_str = str(e)
                if "PerDay" in err_str:
                    raise
                is_transient = any(code in err_str for code in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED"))
                if is_transient and attempt < max_retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise

    def _think_gemini(self, user_input: str) -> str:
        checkpoint = len(self.gemini_history)
        self.gemini_history.append(
            types.Content(role="user", parts=[types.Part(text=user_input)])
        )

        config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            temperature=0.7,
            tools=AVAILABLE_TOOLS,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        try:
            response = self._call_with_retry(
                lambda: self.gemini_client.models.generate_content(
                    model=self.gemini_model,
                    contents=self.gemini_history,
                    config=config,
                )
            )

            while response.function_calls:
                model_content = response.candidates[0].content
                self.gemini_history.append(model_content)

                tool_response_parts = []
                for fc in response.function_calls:
                    args = dict(fc.args) if fc.args else {}
                    print(f"  [SISTEMA -> TOOL]: executando {fc.name}({json.dumps(args, ensure_ascii=False)})")
                    result = execute_tool(fc.name, args)
                    tool_response_parts.append(
                        types.Part.from_function_response(
                            name=fc.name,
                            response=result,
                        )
                    )

                self.gemini_history.append(
                    types.Content(role="user", parts=tool_response_parts)
                )

                response = self._call_with_retry(
                    lambda: self.gemini_client.models.generate_content(
                        model=self.gemini_model,
                        contents=self.gemini_history,
                        config=config,
                    )
                )

            reply = (response.text or "").strip()
            self.gemini_history.append(
                types.Content(role="model", parts=[types.Part(text=reply)])
            )
            return reply

        except Exception:
            del self.gemini_history[checkpoint:]
            raise

    def _think_groq(self, user_input: str) -> str:
        checkpoint = len(self.groq_history)
        self.groq_history.append({"role": "user", "content": user_input})

        try:
            completion = self._call_with_retry(
                lambda: self.groq_client.chat.completions.create(
                    model=self.groq_model,
                    messages=self.groq_history,
                    tools=GROQ_TOOLS_SCHEMA,
                    tool_choice="auto",
                    temperature=0.7,
                )
            )

            message = completion.choices[0].message

            while message.tool_calls:
                assistant_msg = {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in message.tool_calls
                    ],
                }
                self.groq_history.append(assistant_msg)

                for tc in message.tool_calls:
                    args = json.loads(tc.function.arguments or "{}")
                    print(f"  [SISTEMA -> TOOL]: executando {tc.function.name}({json.dumps(args, ensure_ascii=False)})")
                    result = execute_tool(tc.function.name, args)
                    self.groq_history.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )

                completion = self._call_with_retry(
                    lambda: self.groq_client.chat.completions.create(
                        model=self.groq_model,
                        messages=self.groq_history,
                        tools=GROQ_TOOLS_SCHEMA,
                        tool_choice="auto",
                        temperature=0.7,
                    )
                )
                message = completion.choices[0].message

            reply = (message.content or "").strip()
            self.groq_history.append({"role": "assistant", "content": reply})
            return reply

        except Exception:
            del self.groq_history[checkpoint:]
            raise

    def think(self, user_input: str) -> str:
        """Processa a entrada do usuário, acionando fallback para Groq se o Gemini falhar por cota (429) ou sobrecarga (503)."""
        try:
            if self.provider == "gemini":
                try:
                    return self._think_gemini(user_input)
                except Exception as e:
                    should_fallback = any(
                        code in str(e) for code in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE")
                    )
                    if should_fallback and self.groq_client:
                        print(f"  [SISTEMA -> FALLBACK]: Gemini indisponível ou sem cota. Alternando para Groq ({self.groq_model})...")
                        return self._think_groq(user_input)
                    raise

            return self._think_groq(user_input)

        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                return "Senhor, atingimos o limite diário de requisições da API gratuita. Configure uma chave gratuita do Groq no .env ou aguarde a renovação da cota."
            if "503" in err_str or "UNAVAILABLE" in err_str:
                return "Senhor, os servidores neurais estão sobrecarregados no momento. Tente novamente em alguns segundos."
            return f"Desculpe, encontrei uma falha na comunicação neural: {e}"

    def reset_memory(self) -> None:
        """Reinicia o histórico da conversa atual."""
        self._initialize_provider()

    def close(self) -> None:
        """Encerra o pool de conexões HTTP com segurança ao finalizar."""
        if self.gemini_client and hasattr(self.gemini_client, "close"):
            self.gemini_client.close()
