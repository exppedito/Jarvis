import sys
from dotenv import load_dotenv
from src.brain.llm_client import JarvisBrain
from src.tools.monitor import stop_background_monitor
from src.voice.listener import JarvisListener
from src.voice.speaker import JarvisSpeaker


def main():
    load_dotenv()

    print("Inicializando sistemas centrais do J.A.R.V.I.S...")
    try:
        jarvis = JarvisBrain()
    except Exception as e:
        print(f"[ERRO DE INICIALIZAÇÃO]: {e}")
        sys.exit(1)

    print("\nSelecione o modo de interface:")
    print("  [1] Voz Completa (Microfone + Resposta Falada)")
    print("  [2] Apenas Texto (Console silencioso)")
    mode = input("Opção (padrão 1): ").strip() or "1"

    voice_enabled = mode == "1"
    listener = None
    speaker = None

    if voice_enabled:
        try:
            speaker = JarvisSpeaker()
            listener = JarvisListener()
        except Exception as e:
            print(f"[AVISO ÁUDIO]: Falha ao iniciar subsistema de voz ({e}). Alternando para modo texto.")
            voice_enabled = False

    print(f"\nOnline (Provedor: {jarvis.provider.upper()} | Voz: {'ATIVA' if voice_enabled else 'DESATIVADA'}).")
    if voice_enabled:
        print("Pressione [ENTER] vazio para abrir o microfone, digite uma mensagem ou 'sair' para encerrar.\n")
        speaker.speak("Sistemas de áudio online. Às suas ordens, senhor.")
    else:
        print("Digite sua mensagem, 'limpar' para resetar a memória ou 'sair' para encerrar.\n")

    try:
        while True:
            if voice_enabled:
                raw_input = input("Você [ENTER p/ falar ou digite]: ").strip()
                if raw_input == "":
                    user_text = listener.listen_push_to_talk()
                    if not user_text:
                        print("  [SISTEMA]: Nenhuma fala detectada.\n")
                        continue
                    print(f"Você (voz): {user_text}")
                else:
                    user_text = raw_input
            else:
                user_text = input("Você: ").strip()
                if not user_text:
                    continue

            if user_text.lower() in {"sair", "exit", "quit"}:
                farewell = "Encerrando protocolos. Até logo, senhor."
                print(f"J.A.R.V.I.S.: {farewell}")
                if voice_enabled and speaker:
                    speaker.speak(farewell)
                break

            if user_text.lower() == "limpar":
                jarvis.reset_memory()
                msg = "Memória de curto prazo limpa. Podemos recomeçar."
                print(f"J.A.R.V.I.S.: {msg}\n")
                if voice_enabled and speaker:
                    speaker.speak(msg)
                continue

            reply = jarvis.think(user_text)
            print(f"J.A.R.V.I.S.: {reply}\n")
            if voice_enabled and speaker:
                speaker.speak(reply)

    except KeyboardInterrupt:
        print("\nJ.A.R.V.I.S.: Interrupção detectada. Desligando.")
    finally:
        stop_background_monitor()
        if speaker:
            speaker.close()
        jarvis.close()


if __name__ == "__main__":
    main()
