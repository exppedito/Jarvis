import os
import time
from google import genai
from google.genai import types
from groq import Groq
from src.brain.prompt import load_system_prompt


class JarvisBrain:
    """Gerencia a comunicação com o LLM, resiliência de rede, personalidade e memória."""

    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "gemini").lower().strip()
        self.system_prompt = load_system_prompt()
        self.gemini_client = None
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
        self.gemini_history: list[types.Content] = []
        self.groq_client = None
        self.groq_history: list[dict] = []

        self._initialize_provider()

    def _initialize_provider(self) -> None:
        if self.provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key or api_key == "sua_chave_aqui":
                raise ValueError("GEMINI_API_KEY não configurada corretamente no arquivo .env.")

            self.gemini_client = genai.Client(api_key=api_key)
            self.gemini_history = []

        elif self.provider == "groq":
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY não configurada no arquivo .env.")

            self.groq_client = Groq(api_key=api_key)
            self.groq_history = [{"role": "system", "content": self.system_prompt}]

        else:
            raise ValueError(f"Provedor '{self.provider}' não suportado. Use 'gemini' ou 'groq'.")

    def _call_with_retry(self, func, max_retries: int = 3):
        """Executa chamadas à API com retentativas e backoff exponencial para erros 503/429."""
        delay = 1.5
        for attempt in range(1, max_retries + 1):
            try:
                return func()
            except Exception as e:
                err_str = str(e)
                is_transient = any(code in err_str for code in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED"))
                if is_transient and attempt < max_retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise

    def think(self, user_input: str) -> str:
        """Processa a entrada do usuário e retorna a resposta mantendo o histórico da sessão."""
        try:
            if self.provider == "gemini":
                self.gemini_history.append(
                    types.Content(role="user", parts=[types.Part(text=user_input)])
                )
                try:
                    response = self._call_with_retry(
                        lambda: self.gemini_client.models.generate_content(
                            model=self.gemini_model,
                            contents=self.gemini_history,
                            config=types.GenerateContentConfig(
                                system_instruction=self.system_prompt,
                                temperature=0.7,
                            ),
                        )
                    )
                except Exception:
                    # Remove a pergunta não respondida para manter a alternância user/model íntegra
                    self.gemini_history.pop()
                    raise

                reply = response.text.strip()
                self.gemini_history.append(
                    types.Content(role="model", parts=[types.Part(text=reply)])
                )
                return reply

            if self.provider == "groq":
                self.groq_history.append({"role": "user", "content": user_input})
                try:
                    completion = self._call_with_retry(
                        lambda: self.groq_client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=self.groq_history,
                            temperature=0.7,
                        )
                    )
                except Exception:
                    self.groq_history.pop()
                    raise

                reply = completion.choices[0].message.content.strip()
                self.groq_history.append({"role": "assistant", "content": reply})
                return reply

        except Exception as e:
            err_str = str(e)
            if "503" in err_str or "UNAVAILABLE" in err_str:
                return "Senhor, os servidores neurais estão enfrentando um pico de tráfego neste instante. Tente novamente em alguns segundos."
            return f"Desculpe, encontrei uma falha inesperada na comunicação neural: {e}"

    def reset_memory(self) -> None:
        """Reinicia o histórico da conversa atual."""
        self._initialize_provider()

    def close(self) -> None:
        """Encerra o pool de conexões HTTP com segurança ao finalizar."""
        if self.gemini_client and hasattr(self.gemini_client, "close"):
            self.gemini_client.close()
