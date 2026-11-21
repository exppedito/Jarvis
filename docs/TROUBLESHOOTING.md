# 🛠️ Troubleshooting & Diário de Engenharia

Registro cronológico dos incidentes técnicos encontrados durante o desenvolvimento do J.A.R.V.I.S., detalhando o diagnóstico de causa raiz, a resolução aplicada e a justificativa arquitetural de cada solução.

---

## Incidente 01 — Encerramento Prematuro do Cliente HTTP (`Cannot send a request, as the client has been closed`)

* **O Problema:** Ao iniciar o módulo conversacional (`python -m src.main`) e enviar a primeira mensagem, o assistente falhava ao tentar se comunicar com a API do Gemini, retornando a exceção `Cannot send a request, as the client has been closed`.
* **Por que aconteceu (Causa Raiz):** Na implementação inicial de `JarvisBrain._initialize_provider()`, o objeto `genai.Client(api_key=api_key)` foi atribuído a uma variável local (`client`). Assim que o método de inicialização concluía sua execução, o *Garbage Collector* do Python detectava que não havia referências ativas ao objeto, desalocava-o da memória e encerrava o pool de conexões HTTP subjacente (`httpx`). Quando `send_message()` era invocado posteriormente no loop principal, o canal de transporte já estava fechado.
* **Como foi sanado:** Promovemos a instância do cliente para um atributo da própria classe (`self.gemini_client = genai.Client(...)`) e implementamos o método `close()` chamado no bloco `finally` do `main.py`.
* **Validação e Justificativa Técnica:** Após a alteração, o erro de conexão fechada foi eliminado e o terminal passou a encerrar o processo sem travar o shell. Manter o cliente vinculado ao ciclo de vida da instância `JarvisBrain` reaproveita o pool de conexões TCP/TLS durante toda a sessão (reduzindo a latência entre perguntas) e garante liberação limpa de recursos ao sair.

---

## Incidente 02 — Modelo Descontinuado na API (`404 NOT_FOUND: models/gemini-2.5-flash`)

* **O Problema:** Após estabilizar a conexão HTTP, a primeira requisição real ao endpoint retornou erro HTTP `404 NOT_FOUND`, informando que `models/gemini-2.5-flash` não está mais disponível para novos usuários e recomendando a migração para `models/gemini-3.8-flash`.
* **Por que aconteceu (Causa Raiz):** O identificador do modelo estava fixo (*hardcoded*) no código-fonte apontando para uma geração anterior que sofreu *deprecation* no Google AI Studio para chaves recém-criadas.
* **Como foi sanado:** Atualizamos o modelo padrão para `gemini-3.8-flash` e desacoplamos sua definição através da leitura de variável de ambiente (`os.getenv("GEMINI_MODEL", "gemini-3.8-flash")`).
* **Validação e Justificativa Técnica:** Ao executar `python -m src.main`, o J.A.R.V.I.S. estabeleceu a sessão com sucesso e respondeu respeitando as diretrizes de personalidade sem Markdown. Externalizar o identificador do modelo para variáveis de ambiente segue o princípio de configuração desacoplada (*Twelve-Factor App*), permitindo futuras atualizações de versão sem alteração no código-fonte.

---

## Incidente 03 — Instabilidade Transitória em Picos de Demanda (`503 UNAVAILABLE`)

* **O Problema:** Durante diálogos sequenciais no terminal, a primeira pergunta era respondida normalmente, mas perguntas subsequentes falhavam intermitentemente com erro HTTP `503 UNAVAILABLE` (*"This model is currently experiencing high demand"*), expondo um dicionário JSON bruto na saída do assistente.
* **Por que aconteceu (Causa Raiz):** Endpoints gratuitos de inferência em nuvem sofrem oscilações momentâneas de capacidade. O cliente HTTP executava apenas uma tentativa síncrona sem mecanismo de tolerância a falhas transitórias, além de acoplar o histórico dentro de um objeto de sessão opaco.
* **Como foi sanado:** Implementamos o padrão **Retry com Exponential Backoff** (`_call_with_retry`, com até 3 tentativas e intervalos crescentes de `1.5s` e `3.0s` para códigos `503` e `429`), desacoplamos o histórico de mensagens em uma lista explícita (`self.gemini_history`) com *rollback* (`pop()`) em caso de falha e substituímos exceções brutas por respostas alinhadas à personalidade do assistente.
* **Validação e Justificativa Técnica:** Nos testes em sequência, o J.A.R.V.I.S. manteve a continuidade do diálogo e a memória contextual mesmo sob oscilações da API. Essa é a abordagem padrão em sistemas distribuídos porque absorve micro-indisponibilidades sem intervenção do usuário, preserva a integridade da alternância `user/model` no histórico e impede vazamento de stack traces na interface de voz.
