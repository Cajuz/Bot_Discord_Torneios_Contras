```markdown
# 🎮 X1 Frifas — Discord Bot

Bot de gerenciamento de partidas 1x1 para servidores Discord, com sistema de filas,
mediadores, suporte via ticket, anti-spam, onboarding automático e painel de saúde
em tempo real.

---

## 🧰 Tecnologias

| Camada       | Tecnologia                          |
|--------------|-------------------------------------|
| Linguagem    | Python 3.11+                        |
| Framework    | discord.py (`discord` + `commands`) |
| Banco        | MongoDB (async via `motor`)         |
| Config       | `python-dotenv`                     |
| Container    | Docker + Docker Compose             |
| Versionamento| Git + GitHub                        |

---

## 📁 Estrutura do Projeto

```text
x1_frifas/
├── src/
│   ├── main.py                          # Entrypoint principal
│   ├── config/
│   │   ├── database.py                  # Conexão MongoDB (motor)
│   │   ├── discord_bot.py               # Factory e start do bot
│   │   ├── channels_config.py           # Categorias, canais e valores de aposta
│   │   └── rules.py                     # Embed das regras do servidor
│   ├── services/
│   │   ├── channel_service.py           # Setup completo de canais e cargos
│   │   ├── match_service.py             # CRUD de partidas
│   │   ├── match_queue_service.py       # Lógica de fila de partidas
│   │   ├── mediator_queue.py            # Fila e roteamento de mediadores
│   │   ├── thread_reuse_service.py      # Pool de threads arquivadas
│   │   ├── thread_log_service.py        # Log de conteúdo de threads
│   │   ├── onboarding_service.py        # Fluxo de entrada + CAPTCHA via DM
│   │   ├── anti_spam_service.py         # Detecção e bloqueio de spam
│   │   ├── health_check_service.py      # Diagnóstico em tempo real do sistema
│   │   └── mediador_dashboard_service.py# Dashboard diário de partidas
│   ├── views/
│   │   ├── match_queue_view.py          # Cards interativos de fila
│   │   ├── mediator_panel_view.py       # Painel dos mediadores
│   │   ├── match_thread_view.py         # Controles dentro da thread de partida
│   │   ├── ticket_view.py               # Sistema de tickets de suporte
│   │   ├── spam_block_card_view.py      # Card de membro bloqueado por spam
│   │   └── health_check_view.py         # Embed + botões do health check
│   └── utils/
│       └── logger.py                    # Logger colorido customizado
├── .env                                 # Variáveis de ambiente (não versionar!)
├── .env.example                         # Template de variáveis
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## ⚙️ Requisitos

- Python **3.11** ou superior
- MongoDB **6.0** ou superior (local ou Atlas)
- Token de Bot Discord com as seguintes **Intents** habilitadas no Portal:
  - `MESSAGE CONTENT`
  - `SERVER MEMBERS`
  - `GUILDS`
- Permissões do bot no servidor:
  - `Administrator` (recomendado para setup inicial)

---

## 🔑 Variáveis de Ambiente

Crie um arquivo `.env` na raiz (use `.env.example` como base):

```env
# Discord
DISCORD_TOKEN=seu_token_aqui
COMMAND_PREFIX=!

# MongoDB
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=x1_frifas
```

---

## 🚀 Instalação e Execução

### Opção 1 — Python direto

```bash
# 1. Clone o repositório
git clone https://github.com/Cajuz/X1_frifas-Discord_bot.git
cd X1_frifas-Discord_bot

# 2. Crie e ative o ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
.venv\Scripts\activate           # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure o .env
cp .env.example .env
# Edite o .env com seu token e URI do MongoDB

# 5. Execute
python src/main.py
```

### Opção 2 — Docker Compose (recomendado)

```bash
# 1. Clone o repositório
git clone https://github.com/Cajuz/X1_frifas-Discord_bot.git
cd X1_frifas-Discord_bot

# 2. Configure o .env
cp .env.example .env
# Edite o .env com seu token

# 3. Suba os containers
docker compose up -d

# 4. Acompanhe os logs
docker compose logs -f bot
```

---

## 🐳 Docker

### `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

CMD ["python", "src/main.py"]
```

### `docker-compose.yml`

```yaml
version: "3.9"

services:
  bot:
    build: .
    container_name: x1_frifas_bot
    restart: unless-stopped
    env_file:
      - .env
    depends_on:
      mongo:
        condition: service_healthy
    volumes:
      - ./src:/app/src
    networks:
      - x1net

  mongo:
    image: mongo:6.0
    container_name: x1_frifas_mongo
    restart: unless-stopped
    environment:
      MONGO_INITDB_DATABASE: x1_frifas
    volumes:
      - mongo_data:/data/db
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - x1net

volumes:
  mongo_data:

networks:
  x1net:
    driver: bridge
```

### Comandos Docker úteis

```bash
# Subir em background
docker compose up -d

# Ver logs em tempo real
docker compose logs -f bot

# Reiniciar apenas o bot (após mudanças de código)
docker compose restart bot

# Rebuild completo após mudanças no Dockerfile ou requirements
docker compose up -d --build

# Parar tudo
docker compose down

# Parar e remover volumes (APAGA dados do MongoDB)
docker compose down -v
```

---

## 🏗️ Primeiro Setup no Servidor Discord

Após o bot estar online, execute no Discord como **Administrador**:

```
!setupcanais
```

Isso criará automaticamente toda a estrutura abaixo:

| Posição | Categoria          | Canais criados                                                   |
|---------|--------------------|------------------------------------------------------------------|
| 0       | 📈 ANALYTICS       | `#dashboard-partidas`, `#historico-partidas`, `#logs-partidas`   |
| 1       | 📊 DASHBOARD       | `#health-check`                                                  |
| 2       | 🚫 BANS-CONTROL    | `#membros-bloqueados`                                            |
| 3       | ℹ️ INFORMAÇÕES     | `#📜regras`, `#📢avisos`                                          |
| 4       | 🧑‍⚖️ MEDIADORES     | `#painel-mediadores`, `#chat-mediadores`                         |
| 5       | 🎫 SUPORTE         | `#suporte`, `#chat-suporte`, `#chamados-suporte`, `#chat-chamados`|
| 6+      | Categorias de jogo | Canais configurados em `channels_config.py`                      |

**Cargos criados automaticamente:**

| Cargo        | Cor       | Função                              |
|--------------|-----------|-------------------------------------|
| `Membro`     | 🟢 Verde  | Liberado após aceitar as regras     |
| `Controller` | 🔵 Azul   | Mediadores de partida               |
| `Suporte`    | 🟣 Roxo   | Equipe de atendimento               |
| `ADM`        | 🔴 Vermelho| Administradores                    |
| `Bloqueado`  | ⚫ Padrão | Membros bloqueados por spam         |

---

## 🎮 Funcionalidades

### 🔁 Sistema de Filas e Partidas
- Cards interativos por canal com valores de aposta: `R$2`, `R$5`, `R$10`, `R$20`, `R$50`, `R$100`, `R$200`
- Modalidades: **GEL NORMAL** e **GEL INFINITO** (exclusivo `1x1-mob`)
- Partidas gerenciadas em threads privadas com painel de controle completo
- Fluxo: Fila → Confirmação → Pagamento → Início → Resultado → Prêmio

### 🧑‍⚖️ Mediadores
- Fila rotativa com rate-limit (máx. 5 partidas a cada 8 minutos)
- Painel interativo com botões para entrar/sair da fila
- Sincronização automática pelo cargo `Controller`
- Dashboard diário com estatísticas

### 🧵 Pool de Threads
- Reuso de threads arquivadas para evitar o limite de 1.000 threads ativas do Discord
- Pré-aquecimento configurável por canal
- Validação automática do pool na inicialização

### 🎫 Suporte via Ticket
- Abertura de chamados com categorias selecionáveis
- Atribuição de atendente com botão **Assumir**
- Fluxo por DM + histórico persistente no MongoDB
- Limite de 1 chamado ativo por usuário

### 🛡️ Anti-Spam & Onboarding
- Detecção automática de flood e bloqueio com cargo `Bloqueado`
- Onboarding via DM ao entrar no servidor (30 min para aceitar)
- CAPTCHA integrado antes de liberar o cargo `Membro`
- Restauração de bloqueios após reinicialização

### 🏥 Health Check
- Diagnóstico em tempo real de 6 categorias: Infra, Threads, Partidas, Mediadores, Spam, Suporte
- Score visual (0–100%) com barra de progresso por categoria
- Painel interativo com botões por categoria e botão de atualização
- Postado automaticamente no `#health-check` após `!setupcanais`

---

## 📋 Referência de Comandos

### Membros
| Comando               | Descrição                                |
|-----------------------|------------------------------------------|
| `!perfil [@usuario]`  | Ver perfil e estatísticas                |
| `!partidas`           | Listar partidas ativas                   |
| `!statuscanal [nome]` | Estatísticas de um canal de partidas     |
| `!fila`               | Ver mediadores disponíveis               |
| `!fechar_chamado <id>`| Fechar chamado de suporte ativo          |

### Mediadores (`Controller` ou `ADM`)
| Comando                    | Descrição                              |
|----------------------------|----------------------------------------|
| `!addmediador`             | Entrar na fila de mediadores           |
| `!removemediador`          | Sair da fila de mediadores             |
| `!menu_partida`            | Receber painel de controle via DM      |
| `!confirmar_pagamento`     | Confirmar recebimento do pagamento     |
| `!iniciar_partida`         | Iniciar partida após confirmar         |
| `!winner_team blue\|red`   | Declarar time vencedor                 |
| `!prize`                   | Confirmar entrega do prêmio            |
| `!cancelar_match [motivo]` | Cancelar partida da thread atual       |

### Suporte (`Suporte` ou `ADM`)
| Comando                    | Descrição                              |
|----------------------------|----------------------------------------|
| `!concluir_chamado <id>`   | Marcar chamado como resolvido          |

### Administradores
| Comando                          | Descrição                                        |
|----------------------------------|--------------------------------------------------|
| `!setupcanais`                   | Configura toda estrutura do servidor             |
| `!healthcheck`                   | Exibe painel de saúde do sistema                 |
| `!dashboard`                     | Atualiza o dashboard Analytics manualmente       |
| `!atualizarcards [#canal]`       | Recria cards de um canal específico              |
| `!atualizartodos`                | Recria cards de todos os canais de partida       |
| `!atualizarmediadores`           | Atualiza painel do `#painel-mediadores`          |
| `!sincmediadores`                | Sincroniza fila pelo cargo Controller            |
| `!threadstatus`                  | Status do pool e limite de threads               |
| `!preaquecerpool [#canal] [qtd]` | Pré-cria threads arquivadas (1–10)               |
| `!validarpool`                   | Remove entradas inválidas do pool                |
| `!cancelarpartida <id> [motivo]` | Cancela qualquer partida por ID                  |
| `!forcarconcluir <id>`           | Força finalização de qualquer partida            |
| `!inspecionar <id>`              | Exibe todos os campos da partida no banco        |
| `!simularfila [canal] [v] [gel]` | Simula fila completa para testes                 |
| `!stats`                         | Estatísticas de onboarding do servidor           |
| `!aviso <texto>`                 | Posta aviso no `#avisos` com `@everyone`         |
| `!testarregras`                  | Testa fluxo de onboarding via DM (sem kick)      |
| `!bloquear @user [motivo]`       | Bloqueia manualmente um membro                   |
| `!desbloquear @user`             | Desbloqueia um membro bloqueado                  |

---

## 🤝 Como Contribuir

### 1. Fork e clone

```bash
git clone https://github.com/SEU_USUARIO/X1_frifas-Discord_bot.git
cd X1_frifas-Discord_bot
```

### 2. Crie uma branch para sua feature

```bash
# Padrão: feat/<nome>, fix/<nome>, refactor/<nome>
git checkout -b feat/minha-feature
```

### 3. Desenvolva e commite

```bash
# Instale as dependências de dev
pip install -r requirements.txt

# Faça as alterações...

# Commit seguindo Conventional Commits
git add .
git commit -m "feat: adiciona sistema de ranking por canal"
```

**Padrão de commits:**

| Prefixo     | Quando usar                              |
|-------------|------------------------------------------|
| `feat:`     | Nova funcionalidade                      |
| `fix:`      | Correção de bug                          |
| `refactor:` | Refatoração sem mudança de comportamento |
| `docs:`     | Alterações na documentação               |
| `chore:`    | Tarefas de manutenção (deps, config)     |

### 4. Abra um Pull Request

```bash
git push origin feat/minha-feature
```

Abra o PR no GitHub apontando para a branch `main`. Descreva:
- O que foi alterado
- Como testar
- Se há breaking changes

### 5. Checklist antes do PR

- [ ] Código testado localmente com bot em servidor de teste
- [ ] Sem credenciais ou tokens no código
- [ ] `.env` não commitado (verificar `.gitignore`)
- [ ] Comandos novos documentados em `!help_adm` / `!help_med` / `!help`

---

## 🔒 .gitignore recomendado

```gitignore
# Ambiente
.env
.venv/
__pycache__/
*.pyc
*.pyo

# IDEs
.vscode/
.idea/
*.swp

# Logs
*.log
logs/

# Docker volumes locais
mongo_data/
```

---

## 📄 Licença

Este projeto é de uso privado. Para dúvidas sobre licenciamento, entre em contato
com o mantenedor do repositório.

---

