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

---

## Incidente 04 — Esgotamento da Cota Diária Gratuita (`429 RESOURCE_EXHAUSTED`) e Bloqueio de Retorno da Whitelist

* **O Problema:** Ao solicitar a abertura de um programa não autorizado (*"Abra o editor de registros do windows"*), o assistente não acionava a camada de permissão nem informava os aplicativos permitidos, retornando erro `429 RESOURCE_EXHAUSTED` (`limit: 20` requisições/dia no tier gratuito do `gemini-3.8-flash`).
* **Por que aconteceu (Causa Raiz):** O teto diário de 20 requisições gratuitas do provedor primário havia sido atingido, fazendo a API recusar a requisição antes mesmo da etapa de *Function Calling*. Além disso, o mecanismo de retentativas insistia em erros `429` marcados com `PerDay` (que não se resolvem em segundos), e o núcleo operava sem failover automático entre provedores.
* **Como foi sanado:** Evoluímos `JarvisBrain` (`src/brain/llm_client.py`) para uma arquitetura **Multi-Provider com Failover Automático (`Gemini -> Groq`)**, interrompendo retentativas imediatas quando o erro contém `PerDay`, implementando suporte completo a *Tool Calling* no adaptador do Groq (`GROQ_TOOLS_SCHEMA`) e enriquecendo o retorno de `status: "denied"` em `src/tools/app_launcher.py` e `config/personality.yaml` para listar explicitamente os itens autorizados.
* **Validação e Justificativa Técnica:** O failover transparente entre provedores gratuitos garante continuidade operacional a custo zero: quando a cota diária do provedor primário se esgota, o assistente transfere a inferência e a execução de ferramentas para o provedor secundário sem interrupção para o usuário.

---

## Incidente 05 — Modelo Descontinuado no Provedor de Contingência (`404 model_not_found: llama-3.3-70b-versatile`)

* **O Problema:** Ao acionar o fallback automático para o Groq, a chamada falhou com erro HTTP `404` (`The model llama-3.3-70b-versatile does not exist or you do not have access to it`).
* **Por que aconteceu (Causa Raiz):** O identificador do modelo secundário estava fixo (*hardcoded*) no código-fonte, tornando o caminho de contingência vulnerável ao ciclo de descontinuação de modelos da API do Groq.
* **Como foi sanado:** Implementamos o método `_resolve_groq_model()` em `JarvisBrain`, que consulta dinamicamente o endpoint `groq_client.models.list()` na inicialização, descarta modelos especializados não conversacionais (`whisper`, `tts`, `guard`, `embed`) e seleciona automaticamente o modelo ativo prioritário disponível na conta (ou respeita `GROQ_MODEL` no `.env`).
* **Validação e Justificativa Técnica:** No teste de validação (`python -m src.main`), ao solicitar *"Abra o editor de registros do windows"*, o sistema detectou o limite de cota do Gemini, alternou automaticamente para o modelo ativo `qwen/qwen3.8-27b` no Groq, executou `open_application({"app_name": "regedit"})`, bloqueou o acesso via whitelist e respondeu em linguagem natural listando todos os 7 aplicativos e links autorizados. A descoberta dinâmica de modelos elimina manutenção manual por *deprecation* e assegura resiliência real no failover.

---

## Incidente 06 — Incompatibilidade de Assinatura na Decodificação de Áudio (`TypeError: open() got an unexpected keyword argument 'metadata_errors'`)

* **O Problema:** Na primeira execução do modo de voz (`src/voice/listener.py`), o sintetizador de saída (`Edge-TTS`) funcionou normalmente, mas a captura do microfone falhava na etapa de transcrição com `[ERRO STT]: Falha na transcrição (open() got an unexpected keyword argument 'metadata_errors')`.
* **Por que aconteceu (Causa Raiz):** Ao passar o caminho de um arquivo `.wav` em disco para `WhisperModel.transcribe(tmp_path)`, o `faster-whisper` invoca internamente a biblioteca `PyAV` (`av.open(..., metadata_errors="ignore")`). Versões recentes do `PyAV` no Python 3.12 removeram o argumento `metadata_errors` da assinatura de `av.open()`, quebrando a leitura de arquivos de áudio intermediários.
* **Como foi sanado:** Eliminamos o uso de arquivos `.wav` temporários e convertemos os frames capturados pelo `sounddevice` (`int16`) diretamente em um vetor NumPy 1D `float32` normalizado (`[-1.0, 1.0]`) na memória RAM, passando o array diretamente para `self.model.transcribe(audio_float32, ...)` com verificação prévia de nível RMS.
* **Validação e Justificativa Técnica:** Nos testes subsequentes, o `faster-whisper` transcreveu a fala em português instantaneamente (`Você (voz): ...`). Processar o áudio 100% em RAM (*Zero-Disk I/O*) não apenas contorna a dependência do decodificador externo `PyAV`, como também reduz a latência de transcrição e evita operações desnecessárias de escrita/exclusão no SSD.

---

## Incidente 07 — Failover Não Acionado em Sobrecarga (`503 UNAVAILABLE`) do Provedor Primário

* **O Problema:** Após validar a transcrição de voz no Incidente 06, a requisição falada ao Gemini sofreu sobrecarga (`503 UNAVAILABLE`) e o assistente respondeu que os servidores neurais estavam sobrecarregados em vez de alternar para o Groq.
* **Por que aconteceu (Causa Raiz):** O bloco de contingência em `JarvisBrain.think()` verificava apenas códigos de esgotamento de cota (`429` / `RESOURCE_EXHAUSTED`), não incluindo códigos de indisponibilidade/sobrecarga (`503` / `UNAVAILABLE`) como gatilho de failover.
* **Como foi sanado:** Expandimos a verificação `should_fallback` em `src/brain/llm_client.py` para acionar o provedor secundário (`Groq`) tanto em erros `429`/`RESOURCE_EXHAUSTED` quanto em erros `503`/`UNAVAILABLE` após as retentativas locais.
* **Validação e Justificativa Técnica:** Nos testes ponta a ponta por voz, quando o provedor primário apresentou sobrecarga, o sistema comutou automaticamente para o Groq, executou as ferramentas solicitadas e sintetizou a resposta em áudio sem interrupção. Tratar tanto erros de cota quanto de disponibilidade garante resiliência real em arquiteturas multi-provider.
