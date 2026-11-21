# 🤖 J.A.R.V.I.S. — Assistente Pessoal de Desktop com IA

Assistente pessoal modular desenvolvido em **Python**, inspirado no J.A.R.V.I.S., projetado para operar com **custo zero**, baixo consumo de recursos locais e **controle estrito de permissões** sobre o sistema operacional.

---

## 🎯 Objetivo do Projeto

Construir um assistente de voz e texto fluido, dotado de personalidade própria e capaz de interagir com o computador do usuário (telemetria de hardware, abertura de aplicativos autorizados e automação de rotinas) sem expor o sistema a execuções arbitrárias de comandos.

### Pilares da Arquitetura
* **Custo Zero (100% Gratuito):** Utiliza tiers gratuitos de APIs de inferência em nuvem combinados com processamento local leve de áudio.
* **Arquitetura Híbrida (Low-RAM Footprint):** O raciocínio pesado é delegado para LLMs via API (Google Gemini / Groq), mantendo a GPU local livre e o consumo de RAM abaixo de 600 MB.
* **Segurança por Design (Whitelist):** O modelo de linguagem **nunca** possui acesso direto ao terminal (`CMD`/`Bash`). Toda ação no sistema passa por uma camada de validação baseada em permissões explícitas.

---

## 🧠 Arquitetura e Fluxo de Execução

```text
[Entrada: Voz ou Texto]
          │
          ▼
[1. STT Local (Faster-Whisper INT8)] ──► Transcrição rápida em CPU
          │
          ▼
[2. Cérebro (LLM + System Prompt + Histórico)]
          │
          ├──► (Apenas diálogo) ──────────────────────────┐
          │                                                │
          └──► (Intenção de ação via Function Calling)     │
                    │                                      │
                    ▼                                      │
          [3. Camada de Segurança (permissions.json)]      │
                    │                                      │
                    ▼                                      │
          [4. Execução Isolada (Tools Python)]             │
                    │                                      │
                    ▼                                      │
          [Retorno estruturado para o LLM] ────────────────┤
                                                           ▼
                                            [5. TTS Neural (Edge-TTS)]
                                                           │
                                                           ▼
                                               [Resposta em Áudio/Texto]
```

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia | Papel no Sistema |
| :--- | :--- | :--- |
| **Linguagem** | Python 3.12 | Orquestração geral, assincronismo e integração com o SO. |
| **Cérebro (LLM)** | Google Gemini API / Groq | Processamento de linguagem natural, memória contextual e *Tool Calling*. |
| **Ouvidos (STT)** | Faster-Whisper (`int8`) | Reconhecimento de fala local otimizado para CPU, sem limites de requisição. |
| **Voz (TTS)** | Edge-TTS | Síntese de voz neural em português (`pt-BR-AntonioNeural`) sem necessidade de chave de API. |
| **Telemetria & SO** | `psutil`, `subprocess`, `pynput` | Monitoramento de CPU/RAM/Disco, controle de aplicativos e atalhos globais. |
| **Configuração** | `python-dotenv`, `PyYAML`, JSON | Isolamento de credenciais, ajuste de personalidade e regras de permissão. |

---

## 🔒 Modelo de Segurança

Para mitigar riscos de execução indevida por alucinação do modelo, o assistente opera sob o princípio do **menor privilégio**:
1. O LLM recebe apenas as assinaturas das ferramentas registradas em `src/tools/registry.py`.
2. Quando o usuário solicita uma ação (ex: *"Abrir o VS Code"*), o modelo retorna apenas uma intenção estruturada em JSON.
3. O módulo `app_launcher.py` valida se o alvo existe dentro do arquivo `config/permissions.json` antes de invocar qualquer processo do sistema operacional.

---

## 📁 Estrutura do Repositório

```text
Jarvis/
├── .env.example             # Modelo das variáveis de ambiente necessárias
├── .gitignore               # Bloqueio de credenciais (.env), venv e arquivos temporários
├── requirements.txt         # Dependências fixadas do projeto
├── README.md                # Documentação técnica e guia de instalação
├── config/
│   ├── permissions.json     # Whitelist de aplicativos e diretórios permitidos
│   └── personality.yaml     # Diretrizes de tom, comportamento e identidade do assistente
└── src/
    ├── __init__.py
    ├── main.py              # Loop principal e orquestração dos módulos
    ├── brain/
    │   ├── llm_client.py    # Adaptador de comunicação com Gemini/Groq e histórico
    │   └── prompt.py        # Carregamento dinâmico da personalidade
    ├── voice/
    │   ├── listener.py      # Captura de microfone e transcrição STT
    │   └── speaker.py       # Síntese e reprodução de áudio TTS
    └── tools/
        ├── registry.py      # Definição das ferramentas expostas ao LLM
        ├── system_info.py   # Leitura de telemetria de hardware (CPU, RAM, Disco)
        └── app_launcher.py  # Executor controlado por whitelist
```

---

## 🚀 Como Executar Localmente

### 1. Pré-requisitos
* **Python 3.11+** instalado e adicionado ao `PATH`.
* **FFmpeg** instalado no sistema operacional (necessário para manipulação de áudio).
* Uma chave de API gratuita do [Google AI Studio](https://aistudio.google.com/) (ou [Groq Cloud](https://console.groq.com/)).

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
Copie o arquivo de exemplo e insira sua chave de API:
```bash
cp .env.example .env
```
Edite o arquivo `.env` com suas credenciais:
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=sua_chave_aqui
TTS_VOICE=pt-BR-AntonioNeural
```

### 4. Execução
```bash
python -m src.main
```

---

## 🗺️ Roadmap de Desenvolvimento

- [x] **Fase 1:** Estruturação modular do repositório, isolamento de ambiente e segurança de credenciais.
- [ ] **Fase 2:** Implementação do núcleo conversacional (`brain`) com personalidade customizável e memória de sessão.
- [ ] **Fase 3:** Criação das ferramentas de telemetria de hardware e executor controlado via `permissions.json`.
- [ ] **Fase 4:** Integração da pipeline de áudio bidirecional (STT com Whisper + TTS com Edge-TTS) e atalho global.
