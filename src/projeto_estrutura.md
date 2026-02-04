# 📁 Estrutura Completa do Projeto X1 Free Fire Discord Bot

## Árvore de Diretórios

```
x1-discord-bot/
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
├── requirements.txt                # Dependências Python
├── .gitignore
├── .env.example
├── README.md
├── LICENSE
└── docker-compose.yml              # Composição de containers
```

## Arquivos de Configuração

### 1. **requirements.txt**
```
discord.py==2.4.0
fastapi==0.104.1
uvicorn==0.24.0
motor==3.3.2
pymongo==4.6.0
python-dotenv==1.0.0
pydantic==2.5.0
pydantic-settings==2.1.0
aiohttp==3.9.1
Pillow==10.1.0
numpy==1.26.3
pandas==2.1.3
pytest==7.4.3
pytest-asyncio==0.21.1
```

### 2. **.env.example**
```
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
```

### 3. **.gitignore**
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# IDE
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store

# Ambiente
.env
.env.local
.env.*.local

# Logs
logs/
*.log

# Docker
docker-compose.override.yml

# Tests
.pytest_cache/
.coverage
htmlcov/

# Dados sensíveis
*.key
*.pem
secrets/
```

## Estrutura de Arquivo Principal

### bot/main.py
```python
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} está online!')
    try:
        synced = await bot.tree.sync()
        print(f"Sincronizados {len(synced)} comandos")
    except Exception as e:
        print(f"Erro ao sincronizar: {e}")

if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))
```

### api/main.py
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="X1 Free Fire API",
    description="API para gerenciamento de partidas X1",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### database/mongodb.py
```python
from motor.motor_asyncio import AsyncClient
from os import getenv

MONGO_URI = getenv("MONGO_URI")
DB_NAME = getenv("MONGO_DB_NAME", "x1_bot")

client: AsyncClient = None
db = None

async def connect_db():
    global client, db
    client = AsyncClient(MONGO_URI)
    db = client[DB_NAME]
    print("✓ MongoDB conectado")

async def close_db():
    global client
    if client:
        client.close()
        print("✓ MongoDB desconectado")

async def get_db():
    return db
```

### services/logger_service.py
```python
import logging
import json
from datetime import datetime
from motor.motor_asyncio import AsyncClient

class StructuredLogger:
    def __init__(self, name: str, db):
        self.logger = logging.getLogger(name)
        self.db = db
    
    async def log_event(self, event_type: str, data: dict):
        log_entry = {
            "timestamp": datetime.utcnow(),
            "event_type": event_type,
            "data": data
        }
        await self.db.logs.insert_one(log_entry)
        self.logger.info(f"Event logged: {event_type}")
```

---

## Uso

1. **Clone e configure**
```bash
git clone https://github.com/seu-usuario/x1-discord-bot.git
cd x1-discord-bot
cp .env.example .env
# Edite .env com suas credenciais
```

2. **Instale dependências**
```bash
pip install -r requirements.txt
```

3. **Execute com Docker**
```bash
docker-compose up -d
```

4. **Verifique logs**
```bash
docker-compose logs -f bot
```

---

## Próximas Etapas

✅ Estrutura criada
- [ ] Implementar database layer
- [ ] Criar serviços de negócio
- [ ] Desenvolver comandos do bot
- [ ] Implementar API REST
- [ ] Adicionar testes
- [ ] Configurar CI/CD com GitHub Actions
