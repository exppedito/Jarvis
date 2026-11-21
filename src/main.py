import sys
from dotenv import load_dotenv
from src.brain.llm_client import JarvisBrain


def main():
    # Carrega as chaves do arquivo .env para as variáveis de ambiente do sistema
    load_dotenv()

    print("Inicializando sistemas centrais do J.A.R.V.I.S...")
    try:
        jarvis = JarvisBrain()
    except Exception as e:
        print(f"[ERRO DE INICIALIZAÇÃO]: {e}")
        sys.exit(1)

    print(f"Online (Provedor: {jarvis.provider.upper()}). Digite 'sair' para encerrar ou 'limpar' para resetar a memória.\n")

    while True:
        try:
            user_text = input("Você: ").strip()
            if not user_text:
                continue

            if user_text.lower() in {"sair", "exit", "quit"}:
                print("J.A.R.V.I.S.: Encerrando protocolos. Até logo, senhor.")
                break

            if user_text.lower() == "limpar":
                jarvis.reset_memory()
                print("J.A.R.V.I.S.: Memória de curto prazo limpa. Podemos recomeçar.\n")
                continue

            reply = jarvis.think(user_text)
            print(f"J.A.R.V.I.S.: {reply}\n")

        except KeyboardInterrupt:
            print("\nJ.A.R.V.I.S.: Interrupção detectada. Desligando.")
            break


if __name__ == "__main__":
    main()
