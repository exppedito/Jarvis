import os
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel


class JarvisListener:
    """Captura áudio do microfone e transcreve localmente em CPU usando Faster-Whisper."""

    def __init__(self):
        self.model_size = os.getenv("WHISPER_MODEL", "base").strip()
        self.sample_rate = 16000
        print(f"Carregando modelo auditivo Faster-Whisper ('{self.model_size}' / int8)...")
        self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")

    def listen_push_to_talk(self) -> str:
        """Grava áudio do microfone até o usuário pressionar ENTER e transcreve direto da RAM."""
        frames: list[np.ndarray] = []

        def audio_callback(indata, frame_count, time_info, status):
            frames.append(indata.copy())

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                callback=audio_callback,
            ):
                input("  [OUVINDO...] Fale agora e pressione [ENTER] para enviar: ")
        except Exception as e:
            print(f"  [ERRO MICROFONE]: Falha ao acessar dispositivo de áudio ({e}).")
            return ""

        if not frames:
            return ""

        audio_data = np.concatenate(frames, axis=0)

        # Ignora gravações acidentais muito curtas (< 0.3s)
        if len(audio_data) < int(self.sample_rate * 0.3):
            return ""

        # Converte PCM int16 para vetor 1D float32 [-1.0, 1.0] em memória (ignora PyAV/disco)
        audio_float32 = audio_data.flatten().astype(np.float32) / 32768.0

        rms = float(np.sqrt(np.mean(np.square(audio_float32))))
        if rms < 1e-5:
            print("  [AVISO MICROFONE]: Sinal de áudio zerado. Verifique o microfone padrão do Windows.")
            return ""

        try:
            segments, _ = self.model.transcribe(
                audio_float32,
                language="pt",
                beam_size=5,
                vad_filter=True,
            )
            transcript = " ".join(seg.text.strip() for seg in segments).strip()
            return transcript
        except Exception as e:
            print(f"  [ERRO STT]: Falha na transcrição ({e}).")
            return ""
