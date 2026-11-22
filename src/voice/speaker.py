import asyncio
import os
import tempfile
import time
import edge_tts
import pygame


class JarvisSpeaker:
    """Converte texto em voz neural usando Edge-TTS e reproduz localmente via Pygame."""

    def __init__(self):
        self.voice = os.getenv("TTS_VOICE", "pt-BR-AntonioNeural").strip()
        if not pygame.mixer.get_init():
            pygame.mixer.init()

    async def _synthesize(self, text: str, output_path: str) -> None:
        communicate = edge_tts.Communicate(text=text, voice=self.voice)
        await communicate.save(output_path)

    def speak(self, text: str) -> None:
        """Sintetiza e reproduz o texto em voz alta de forma síncrona."""
        clean_text = (text or "").strip()
        if not clean_text:
            return

        # Cria e fecha o descritor antes de escrever para evitar lock de arquivo no Windows
        tmp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_path = tmp_file.name
        tmp_file.close()

        try:
            asyncio.run(self._synthesize(clean_text, tmp_path))
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.05)
            pygame.mixer.music.unload()
        except Exception as e:
            print(f"  [AVISO TTS]: Não foi possível reproduzir o áudio ({e}).")
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def close(self) -> None:
        """Encerra o mixer de áudio com segurança."""
        if pygame.mixer.get_init():
            pygame.mixer.quit()
