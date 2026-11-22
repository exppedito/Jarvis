# 🤖 J.A.R.V.I.S. — Assistente Pessoal de Desktop com IA

Assistente pessoal modular desenvolvido em **Python**, inspirado no J.A.R.V.I.S., projetado para operar com **custo zero**, baixo consumo de recursos locais e **controle estrito de permissões** sobre o sistema operacional.

---

## 🎯 Objetivo do Projeto

Construir um assistente de voz e texto fluido, dotado de personalidade própria e capaz de interagir com o computador do usuário (telemetria de hardware, monitoramento autônomo, abertura de aplicativos autorizados e automação de rotinas) sem expor o sistema a execuções arbitrárias de comandos.

### Pilares da Arquitetura
* **Custo Zero (100% Gratuito):** Utiliza tiers gratuitos de APIs de inferência em nuvem combinados com processamento local leve de áudio.
* **Arquitetura Híbrida (Low-RAM Footprint):** O raciocínio pesado é delegado para LLMs via API, enquanto a transcrição de voz roda localmente em CPU (`Faster-Whisper INT8` em memória), mantendo a GPU local livre e o consumo de RAM abaixo de 600 MB.
* **Alta Disponibilidade Multi-Provider & Baixa Latência:** Comunicação protegida por *Retry com Exponential Backoff*, `thinking_budget=0` no Gemini Flash, janela deslizante de histórico (*Sliding Window*), teto enxuto de tokens para voz e alternância automática entre provedores (`Google Gemini` $\rightarrow$ `Groq` com descoberta dinâmica de modelos ativos).
* **Segurança por Design (Whitelist):** O modelo de linguagem **nunca** possui acesso direto ao terminal (`CMD`/`Bash`). Toda ação no sistema passa por uma camada de validação baseada em permissões explícitas (`config/permissions.json`) com invocação de processos via `shell=False`.
* **Observabilidade, Self-Health & Áudio Calibrado:** Rastreamentos técnicos são isolados em log rotativo (`logs/jarvis.log`), o assistente monitora sua própria saúde operacional, executa coletas de telemetria em segundo plano e aplica pós-processamento acústico em memória via FFmpeg.

---

## 🧠 Arquitetura e Fluxo de Execução

```text
[Entrada: Voz (Push-to-Talk) ou Texto]
          │
          ▼
[1. STT Local (Faster-Whisper INT8 / RAM)] ──► Transcrição rápida em PT-BR
          │
          ▼
[2. Cérebro Low-Latency (Gemini [budget=0] ──(429/503 Fallback)──► Groq + Sliding Window)]
          │                                                               │
          ├──► (Apenas diálogo) ──────────────────────────────────────────┼──► [logs/jarvis.log + Latency Metrics]
          │                                                               │
          └──► (Intenção de ação via Function Calling)
                    │
                    ▼
          [3. Camada de Segurança (permissions.json)]
                    │
                    ▼
          [4. Execução Isolada (Tools + Monitor Daemon)]
                    │
                    ▼
          [Retorno estruturado para o LLM] ───────────────────────────────┐
                                                                          ▼
                                               [5. TTS Neural + Filtro Acústico (FFmpeg)]
                                                                          │
                                                                          ▼
                                                              [Resposta em Áudio/Texto]
```

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia | Papel no Sistema |
| :--- | :--- | :--- |
| **Linguagem** | Python 3.12 | Orquestração geral, assincronismo e integração com o SO. |
| **Cérebro (LLM)** | Google Gemini (`gemini-3.8-flash`, `thinking_budget=0`) + Groq | Processamento de linguagem natural de baixa latência, janela deslizante de memória e failover dinâmico. |
| **Ouvidos (STT)** | Faster-Whisper (`int8`) + `sounddevice` + `numpy` | Captura de microfone e transcrição local em CPU direto da RAM (*Zero-Disk I/O*) com filtro VAD. |
| **Voz (TTS)** | Edge-TTS + `FFmpeg` (Pipe DSP) + `pygame` | Síntese neural em português, equalização acústica em memória, modo `--audition` e reprodução local. |
| **Telemetria & Monitoramento** | `psutil`, `threading`, `subprocess` | Telemetria instantânea, daemon de monitoramento em background, *self-health* e launcher seguro. |
| **Observabilidade & Config** | `logging` (RotatingFileHandler), `python-dotenv`, `PyYAML`, JSON | Isolamento de logs técnicos, métricas de latência, credenciais, personalidade e regras de permissão. |

---

## 🔒 Modelo de Segurança

Para mitigar riscos de execução indevida por alucinação do modelo, o assistente opera sob o princípio do **menor privilégio**:
1. O LLM recebe apenas as assinaturas das ferramentas registradas em `src/tools/registry.py`.
2. Quando o usuário solicita uma ação (ex: *"Abrir a calculadora"* ou *"Abrir o editor de registros"*), o modelo retorna apenas uma intenção estruturada em JSON.
3. O módulo `app_launcher.py` valida se o alvo existe dentro do arquivo `config/permissions.json` e invoca o binário resolvido sem interpretador de shell (`shell=False`). Caso o alvo não esteja autorizado, a execução é bloqueada e o assistente informa os itens permitidos.

---

## 📁 Estrutura do Repositório

```text
Jarvis/
├── .env.example             # Modelo das variáveis de ambiente necessárias
├── .gitignore               # Bloqueio de credenciais (.env), logs/, venv e temporários
├── requirements.txt         # Dependências fixadas do projeto
├── README.md                # Documentação técnica e guia de instalação
├── docs/
│   └── TROUBLESHOOTING.md   # Diário de incidentes, causa raiz e resoluções técnicas
├── config/
│   ├── permissions.json     # Whitelist de aplicativos e diretórios permitidos
│   └── personality.yaml     # Diretrizes de tom, comportamento e identidade do assistente
└── src/
    ├── __init__.py
    ├── main.py              # Loop principal híbrido (voz + texto) e orquestração
    ├── brain/
    │   ├── llm_client.py    # Adaptador Gemini/Groq low-latency, sliding window, failover e tool calling
    │   └── prompt.py        # Carregamento dinâmico da personalidade
    ├── utils/
    │   ├── __init__.py
    │   ├── logger.py        # Logger rotativo em arquivo (logs/jarvis.log)
    │   └── metrics.py       # Rastreador de latência, uptime e failovers do assistente
    ├── voice/
    │   ├── __init__.py
    │   ├── listener.py      # Captura de microfone e transcrição STT em RAM (Faster-Whisper)
    │   └── speaker.py       # Síntese TTS, filtro acústico FFmpeg em memória e CLI --audition
    └── tools/
        ├── __init__.py
        ├── registry.py      # Definição e despacho seguro das ferramentas expostas ao LLM
        ├── system_info.py   # Leitura instantânea de telemetria de hardware (CPU, RAM, Disco)
        ├── monitor.py       # Daemon de monitoramento contínuo em background e self-health
        └── app_launcher.py  # Executor controlado por whitelist (shell=False)
```

---

## 🚀 Como Executar Localmente

### 1. Pré-requisitos
* **Python 3.11+** instalado e adicionado ao `PATH`.
* **FFmpeg** instalado no sistema operacional (necessário para manipulação e filtragem de áudio).
* Microfone e saída de áudio ativos (para o modo voz).
* Uma chave de API gratuita do [Google AI Studio](https://aistudio.google.com/) e/ou [Groq Cloud](https://console.groq.com/).

### 2. Instalação
```bash
# Clone o repositório
git clone [https://github.com/exppedito/Jarvis.git](https://github.com/exppedito/Jarvis.git)
cd Jarvis

# Crie e ative o ambiente virtual
python -m venv venv
source venv/Scripts/activate  # No Linux/macOS: source venv/bin/activate

# Instale as dependências
pip install -r requirements.txt
```

### 3. Configuração das Variáveis de Ambiente
Copie o arquivo de exemplo e insira suas chaves de API:
```bash
cp .env.example .env
```
Edite o arquivo `.env` com suas credenciais:
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=sua_chave_aqui
GROQ_API_KEY=sua_chave_opcional_de_fallback_aqui
TTS_VOICE=pt-BR-AntonioNeural
TTS_RATE=-8%
TTS_PITCH=-13Hz
TTS_TIMBRE=jarvis
WHISPER_MODEL=base
```

### 4. Execução
```bash
# Iniciar o assistente (modo voz ou texto)
python -m src.main

# Testar e comparar perfis vocais no terminal
python -m src.voice.speaker --audition
```

---

## 🗺️ Roadmap de Desenvolvimento

- [x] **Fase 1:** Estruturação modular do repositório, isolamento de ambiente e segurança de credenciais.
- [x] **Fase 2:** Implementação do núcleo conversacional (`brain`) com personalidade customizável, memória de sessão, retry exponencial e diário de troubleshooting.
- [x] **Fase 3:** Criação das ferramentas de telemetria de hardware (`psutil`), executor controlado via `permissions.json` (`shell=False`), failover dinâmico (`Gemini -> Groq`) e loop agêntico de *Function Calling*.
- [x] **Fase 4:** Integração da pipeline de áudio bidirecional (STT local em RAM com Faster-Whisper + TTS neural com Edge-TTS) em modo híbrido voz/texto.
- [x] **Side-Task 01:** Isolamento de stack traces em log rotativo (`logs/jarvis.log`) e sanitização de mensagens de erro na interface.
- [x] **Side-Task 02:** Monitoramento autônomo em segundo plano (picos, quedas e processos ofensores) e telemetria interna (*self-health*) do assistente.
- [x] **Side-Task 03:** Otimização de latência (`thinking_budget=0`, janela deslizante de histórico, teto de tokens e telemetria de tempo de resposta).
- [x] **Side-Task 04:** Calibração acústica provisória via FFmpeg (`TTS_TIMBRE=jarvis`) e CLI de audição comparativa (`--audition`).
- [ ] **v2.0 (Próxima Evolução):** Síntese vocal customizada / clonagem de timbre brasileiro fiel do J.A.R.V.I.S. (via RVC ou Piper TTS local).

---

## 📚 Documentação Complementar

* [Diário de Engenharia & Troubleshooting](docs/TROUBLESHOOTING.md) — Registro detalhado dos desafios técnicos enfrentados durante a construção e suas respectivas soluções.
