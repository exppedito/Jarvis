import asyncio
import io
import os
import re
import subprocess
import sys
import tempfile
import edge_tts
import pygame
from dotenv import load_dotenv
from src.utils.logger import get_logger

logger = get_logger("jarvis.voice.speaker")

JARVIS_AUDIO_FILTER = (
    "equalizer=f=130:t=q:w=1.2:g=5,"
    "equalizer=f=3200:t=q:w=1.5:g=-3,"
    "aecho=0.8:0.85:14:0.16,"
    "acompressor=threshold=-18dB:ratio=2.5:attack=10:release=120"
)


class JarvisSpeaker:
    """Sintetiza e reproduz respostas em voz neural PT-BR calibrada para o timbre do J.A.R.V.I.S."""

    def __init__(
        self,
        voice: str | None = None,
        rate: str | None = None,
        pitch: str | None = None,
        timbre: str | None = None,
    ):
        self.voice = (voice or os.getenv("TTS_VOICE", "pt-BR-AntonioNeural")).strip()
        self.rate = (rate or os.getenv("TTS_RATE", "-8%")).strip()
        self.pitch = (pitch or os.getenv("TTS_PITCH", "-13Hz")).strip()
        self.timbre = (timbre or os.getenv("TTS_TIMBRE", "jarvis")).lower().strip()

        if not pygame.mixer.get_init():
            pygame.mixer.init()

        logger.info(
            "JarvisSpeaker inicializado (voice=%s, rate=%s, pitch=%s, timbre=%s)",
            self.voice,
            self.rate,
            self.pitch,
            self.timbre,
        )

    @staticmethod
    def _clean_text_for_speech(text: str) -> str:
        """Remove marcações de Markdown e símbolos visuais para leitura natural."""
        cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        cleaned = re.sub(r"[`*_#>~]+", "", cleaned)
        cleaned = re.sub(r"^\s*[-•]\s+", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    async def _synthesize_bytes(self, text: str) -> bytes:
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            pitch=self.pitch,
        )
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)

    def _apply_jarvis_timbre(self, audio_bytes: bytes) -> bytes:
        """Aplica equalização barítono e micro-ressonância acústica via FFmpeg em memória."""
        if self.timbre != "jarvis" or not audio_bytes:
            return audio_bytes

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-af",
            JARVIS_AUDIO_FILTER,
            "-f",
            "mp3",
            "pipe:1",
        ]
        try:
            proc = subprocess.run(
                cmd,
                input=audio_bytes,
                capture_output=True,
                check=True,
                timeout=8,
            )
            return proc.stdout if proc.stdout else audio_bytes
        except Exception as e:
            logger.warning("Filtro acústico FFmpeg indisponível, usando áudio neural direto: %s", e)
            return audio_bytes

    def _play_mp3_bytes(self, audio_bytes: bytes) -> None:
        clock = pygame.time.Clock()
        try:
            buffer = io.BytesIO(audio_bytes)
            pygame.mixer.music.load(buffer, "mp3")
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                clock.tick(25)
            pygame.mixer.music.unload()
        except pygame.error:
            tmp_path = ""
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                    tmp.write(audio_bytes)
                    tmp_path = tmp.name
                pygame.mixer.music.load(tmp_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    clock.tick(25)
                pygame.mixer.music.unload()
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)

    def speak(self, text: str) -> None:
        """Converte o texto limpo em fala neural calibrada e reproduz de forma síncrona."""
        clean_text = self._clean_text_for_speech(text)
        if not clean_text:
            return

        try:
            raw_bytes = asyncio.run(self._synthesize_bytes(clean_text))
            final_bytes = self._apply_jarvis_timbre(raw_bytes)
            if final_bytes:
                self._play_mp3_bytes(final_bytes)
        except Exception as e:
            logger.error("Falha na síntese/reprodução TTS (%s): %s", self.voice, e, exc_info=True)
            print(f"  [AVISO VOZ]: Não foi possível reproduzir o áudio ({e}).")

    def close(self) -> None:
        """Libera o subsistema de áudio com segurança."""
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.quit()
        logger.info("JarvisSpeaker encerrado.")


def run_audition() -> None:
    """Reproduz uma frase de demonstração em 4 calibrações vocais para comparação."""
    load_dotenv()
    sample_phrase = (
        "Sistemas calibrados. Todos os protocolos operacionais estão prontos, senhor."
    )

    profiles = [
        {
            "label": "Perfil 1 — Sóbrio Limpo (rate=-8%, pitch=-12Hz, timbre=clean)",
            "rate": "-8%",
            "pitch": "-12Hz",
            "timbre": "clean",
        },
        {
            "label": "Perfil 2 — Barítono Profundo (rate=-10%, pitch=-16Hz, timbre=clean)",
            "rate": "-10%",
            "pitch": "-16Hz",
            "timbre": "clean",
        },
        {
            "label": "Perfil 3 — J.A.R.V.I.S. Cinema / Cabine [PADRÃO] (rate=-8%, pitch=-13Hz, timbre=jarvis)",
            "rate": "-8%",
            "pitch": "-13Hz",
            "timbre": "jarvis",
        },
        {
            "label": "Perfil 4 — Original Sem Ajuste / TikTok (rate=+0%, pitch=+0Hz, timbre=clean)",
            "rate": "+0%",
            "pitch": "+0Hz",
            "timbre": "clean",
        },
    ]

    speaker = JarvisSpeaker(voice="pt-BR-AntonioNeural")
    try:
        for idx, p in enumerate(profiles, start=1):
            print(f"[{idx}/{len(profiles)}] {p['label']}")
            speaker.rate = p["rate"]
            speaker.pitch = p["pitch"]
            speaker.timbre = p["timbre"]
            speaker.speak(sample_phrase)
            pygame.time.wait(700)
    finally:
        speaker.close()

    print("\nAudição concluída! Para personalizar no .env, ajuste:")
    print("  TTS_VOICE=pt-BR-AntonioNeural")
    print("  TTS_RATE=-8%")
    print("  TTS_PITCH=-13Hz")
    print("  TTS_TIMBRE=jarvis   # ou 'clean'")


if __name__ == "__main__":
    if "--audition" in sys.argv:
        run_audition()
    else:
        load_dotenv()
        s = JarvisSpeaker()
        s.speak("Sistemas de áudio online. Às suas ordens, senhor.")
        s.close()
