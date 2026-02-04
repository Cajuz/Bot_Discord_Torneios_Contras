X1_Frifas/
│
├── 📂 src/                          # Código-fonte principal
│   ├── 📂 bot/
│   │   ├── __init__.py
│   │   ├── main.py                 # Entry point do bot
│   │   ├── config.py               # Configurações do bot
│   │   └── 📂 cogs/                # Componentes do bot
│   │       ├── __init__.py
│   │       ├── player_commands.py   # Comandos do jogador
│   │       ├── mediador_commands.py # Comandos do mediador
│   │       ├── match_events.py      # Eventos de partida
│   │       └── admin_commands.py    # Comandos admin
│   │
│   ├── 📂 api/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app
│   │   ├── routes.py               # Rotas da API
│   │   └── 📂 endpoints/
│   │       ├── __init__.py
│   │       ├── matches.py
│   │       ├── players.py
│   │       └── mediadores.py
│   │
│   ├── 📂 database/
│   │   ├── __init__.py
│   │   ├── mongodb.py              # Conexão MongoDB
│   │   ├── models.py               # Modelos de dados
│   │   └── 📂 collections/
│   │       ├── __init__.py
│   │       ├── matches.py
│   │       ├── players.py
│   │       ├── mediadores.py
│   │       └── logs.py
│   │
│   ├── 📂 services/
│   │   ├── __init__.py
│   │   ├── match_service.py        # Lógica de partidas
│   │   ├── player_service.py       # Lógica de jogadores
│   │   ├── mediador_service.py     # Lógica de mediadores
│   │   └── logger_service.py       # Logging estruturado
│   │
│   ├── 📂 utils/
│   │   ├── __init__.py
│   │   ├── decorators.py           # Decoradores úteis
│   │   ├── validators.py           # Validadores
│   │   ├── enums.py                # Enumerações
│   │   └── constants.py            # Constantes
│   │
│   └── 📂 discord_components/
│       ├── __init__.py
│       ├── buttons.py              # Componentes de botão
│       ├── selects.py              # Componentes de seleção
│       ├── modals.py               # Formulários modais
│       └── embeds.py               # Embeds formatados
│
├── 📂 config/                      # Arquivos de configuração
│   ├── .env.example
│   ├── settings.py
│   └── logging_config.py
│
├── 📂 tests/                       # Testes unitários
│   ├── __init__.py
│   ├── test_bot.py
│   ├── test_api.py
│   └── test_services.py
│
├── 📂 docker/
│   ├── Dockerfile                  # Container do bot
│   ├── Dockerfile.api              # Container da API
│   ├── docker-compose.yml          # Orquestração
│   └── .dockerignore
│
├── 📂 .github/
│   └── 📂 workflows/
│       └── ci-cd.yml               # GitHub Actions
│
├── 📂 logs/                        # Diretório de logs (gitignore)
│
├── requirements.txt                # Dependências 
├── .gitignore
├── .env.example
├── README.md
├── LICENSE
└── docker-compose.yml              # Composição de containers

### 2. **.env.example**

# Discord
DISCORD_TOKEN=seu_token_aqui
DISCORD_PREFIX=!
DISCORD_SERVER_ID=000000000000000000

# MongoDB
MONGO_URI=mongodb+srv://usuario:senha@cluster.mongodb.net/x1_bot?retryWrites=true&w=majority
MONGO_DB_NAME=x1_bot

# FastAPI
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=False

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/bot.log

# Ambiente
ENVIRONMENT=development





