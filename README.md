<div align="center">

# 🎮 X1 Frifas — Discord Bot

**Bot completo de gestão de partidas mediadas para Free Fire**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![discord.py](https://img.shields.io/badge/discord.py-2.4.0-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discordpy.readthedocs.io/)
[![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47A248?style=flat-square&logo=mongodb&logoColor=white)](https://cloud.mongodb.com/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?style=flat-square&logo=railway&logoColor=white)](https://railway.app/)

</div>

---

## 📋 Sumário

- [Visão Geral](#-visão-geral)
- [Funcionalidades](#-funcionalidades)
- [Requisitos](#-requisitos)
- [Instalação Local (sem Docker)](#-instalação-local-sem-docker)
- [Instalação com Docker](#-instalação-com-docker)
- [Deploy em Cloud (Railway)](#-deploy-em-cloud-railway)
- [Deploy em VPS (systemd)](#-deploy-em-vps-systemd)
- [Variáveis de Ambiente](#-variáveis-de-ambiente)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Primeiro Setup do Servidor](#-primeiro-setup-do-servidor)
- [Perfis de Usuário](#-perfis-de-usuário)
- [Links Úteis](#-links-úteis)

---

## 🎯 Visão Geral

O **X1 Frifas Bot** gerencia todo o ciclo de vida de partidas 1x1, 2x2, 3x3 e 4x4 de Free Fire com apostas em dinheiro real. Centraliza filas, mediação, pagamento PIX, suporte, análise de denúncias e renovação de licença de mediadores — tudo dentro do Discord, sem ferramentas externas.

### Fluxo Resumido

```
Jogador entra na fila (botão)
    → Fila completa → Thread criada automaticamente
    → Mediador conduz: pagamento → partida → vencedor → prêmio
    → Thread devolvida ao pool para reutilização
```

---

## ✨ Funcionalidades

| Módulo | Descrição |
|--------|----------|
| 🎮 **Partidas** | Filas por modo/valor, cards interativos, threads automáticas |
| ⚖️ **Mediação** | Confirmação de pagamento, definição de vencedor, entrega de prêmio |
| 🎫 **Suporte** | Sistema de tickets com canais privados por atendente |
| 🔍 **Análise** | Denúncias de hack, fila de casos, blacklist integrada |
| 🚫 **Blacklist** | Consulta pública por auto-verificação ou Discord ID |
| 💳 **PIX / Renovação** | Licença de mediador via Efí Pay, QR Code por DM, webhook automático |
| 📊 **Dashboards** | Analytics em tempo real: partidas, mediadores, suporte, ranking |
| 📣 **Influencers** | Cadastro, código de convite, comissão, ranking |
| 🔄 **Thread Pool** | Reutilização de threads para economizar o limite do Discord |
| 🏥 **Health Check** | Painel técnico de status do bot e banco de dados |
| 🛡️ **Anti-Spam** | Bloqueio automático de flood e rate limit |

---

## 📦 Requisitos

### Software

| Requisito | Versão mínima | Observação |
|-----------|--------------|------------|
| **Python** | 3.11+ | Usar exatamente 3.11 para compatibilidade com as libs |
| **pip** | 23+ | Incluído com Python |
| **Git** | qualquer | Para clonar o repositório |
| **Docker** *(opcional)* | 24+ | Somente para rodar com container |
| **Docker Compose** *(opcional)* | 2.20+ | Somente para rodar com container |

### Serviços Externos

| Serviço | Obrigatório | Para que serve |
|---------|------------|----------------|
| **Discord Bot Token** | ✅ Sim | Conectar o bot ao Discord |
| **MongoDB Atlas** | ✅ Sim | Banco de dados (tier M0 gratuito funciona) |
| **Efí Pay (Gerencianet)** | ⚠️ Opcional | Cobrança PIX automática para renovação de mediadores |
| **URL Pública (webhook)** | ⚠️ Opcional | Apenas se usar Efí Pay (ex: Railway, VPS com IP) |

---

## 🖥️ Instalação Local (sem Docker)

### 1. Clonar o repositório

```bash
git clone https://github.com/Cajuz/X1_frifas-Discord_bot.git
cd X1_frifas-Discord_bot
```

### 2. Criar ambiente virtual (recomendado)

```bash
# Criar
python -m venv .venv

# Ativar — Linux / macOS
source .venv/bin/activate

# Ativar — Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Ativar — Windows (CMD)
.venv\Scripts\activate.bat
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt

# Opcional: se for usar renovação PIX com Efí Pay
pip install efipay
```

### 4. Configurar variáveis de ambiente

```bash
# Copie o arquivo de exemplo
cp .env.example .env

# Abra e preencha os valores reais
nano .env   # ou code .env / notepad .env
```

> **Variáveis obrigatórias para rodar:** `DISCORD_TOKEN` e `MONGO_URI`
> As demais são opcionais (Efí Pay só é necessário para renovação via PIX).

### 5. Iniciar o bot

```bash
python src/main.py
```

Quando aparecer na saída:
```
✅ MongoDB conectado!
✅ Bot online: X1Frifas#0000
✅ Bot totalmente inicializado!
```
O bot está funcionando. Agora execute `!setupcanais` em qualquer canal do servidor para configurar toda a estrutura.

---

## 🐳 Instalação com Docker

### Pré-requisitos
- Docker 24+ instalado
- Docker Compose 2.20+ instalado

### 1. Configurar variáveis de ambiente

```bash
cp .env.example .env
nano .env   # preencha DISCORD_TOKEN e MONGO_URI no mínimo
```

### 2. Build e iniciar

```bash
# Build e iniciar em background
docker compose up -d --build

# Ver logs em tempo real
docker compose logs -f
```

### 3. Verificar se está rodando

```bash
docker compose ps
```

A coluna `STATUS` deve mostrar `Up`.

### Comandos úteis do Docker

```bash
# Parar o bot
docker compose down

# Reiniciar o bot (após atualizar código)
docker compose up -d --build

# Ver logs das últimas 100 linhas
docker compose logs --tail=100

# Acessar o container
docker compose exec bot bash
```

> 💡 **Dica:** O `Dockerfile` já usa `python:3.11-slim`, instala todas as dependências e define `PYTHONPATH=/app/src` automaticamente.

---

## ☁️ Deploy em Cloud (Railway)

O Railway é a plataforma recomendada para rodar o bot 24/7 com custo mínimo (~$5/mês).

### 1. Configurar MongoDB Atlas

1. Acesse [cloud.mongodb.com](https://cloud.mongodb.com) e crie uma conta
2. Crie um cluster **M0 Free Tier**
3. Em **Database Access** → crie um usuário com senha forte
4. Em **Network Access** → **Add IP Address** → **Allow Access from Anywhere** (`0.0.0.0/0`)
5. Em **Clusters** → **Connect** → **Connect your application** → copie a URI:
   ```
   mongodb+srv://<usuario>:<senha>@<cluster>.mongodb.net/x1frifas?retryWrites=true&w=majority
   ```

### 2. Subir código no GitHub

```bash
# Se ainda não tem repositório:
git init && git add . && git commit -m "inicial"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/x1frifas-bot.git
git push -u origin main

# Atualizar código existente:
git add . && git commit -m "atualização" && git push
```

### 3. Criar projeto no Railway

1. Acesse [railway.app](https://railway.app) → login com GitHub
2. **New Project** → **Deploy from GitHub repo**
3. Selecione o repositório do bot
4. Railway detecta o `Dockerfile` automaticamente ✅

### 4. Configurar variáveis no Railway

No painel do projeto: **serviço** → aba **Variables** → **New Variable**:

```env
DISCORD_TOKEN        = seu_token_do_discord
MONGO_URI            = mongodb+srv://usuario:senha@cluster.mongodb.net/x1frifas?...
MONGO_DB_NAME        = x1frifas
EFI_CLIENT_ID        = seu_client_id_efi
EFI_CLIENT_SECRET    = seu_client_secret_efi
EFI_PIX_KEY          = sua_chave_pix
EFI_SANDBOX          = false
WEBHOOK_BASE_URL     = https://SEU-PROJETO.up.railway.app
RENEWAL_PRICE_7D     = 10.00
RENEWAL_PRICE_15D    = 18.00
RENEWAL_PRICE_30D    = 25.00
LOG_LEVEL            = INFO
```

### 5. Gerar domínio público (necessário para webhook PIX)

1. No Railway: **Settings** → **Networking** → **Generate Domain**
2. Copie a URL gerada (ex: `x1frifas-bot.up.railway.app`)
3. Atualize `WEBHOOK_BASE_URL` com essa URL
4. No painel da Efí Pay, configure o webhook:
   ```
   https://x1frifas-bot.up.railway.app/webhook/efi
   ```

### 6. Deploy

Após salvar as variáveis, clique em **Deploy**. Acompanhe na aba **Logs**:

```
✅ MongoDB conectado!
✅ Bot online: X1Frifas#0000
✅ Bot totalmente inicializado!
```

### 7. CI/CD automático

A cada `git push` na branch `main`, o Railway realiza deploy automático em ~1 minuto.

### Planos Railway

| Plano | Custo | Ideal para |
|-------|-------|------------|
| Hobby | $5/mês | ✅ Bot Discord (uso típico: $2–4/mês) |
| Pro | $20/mês | Múltiplos serviços / alto volume |

---

## 🖥️ Deploy em VPS (systemd)

Para rodar em VPS Linux (Ubuntu/Debian) com reinício automático.

### 1. Preparar o servidor

```bash
# Atualizar pacotes
sudo apt update && sudo apt upgrade -y

# Instalar Python 3.11 e pip
sudo apt install -y python3.11 python3.11-venv python3-pip git
```

### 2. Clonar e configurar

```bash
# Clonar o repositório
git clone https://github.com/Cajuz/X1_frifas-Discord_bot.git /opt/x1frifas
cd /opt/x1frifas

# Criar ambiente virtual e instalar dependências
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configurar variáveis
cp .env.example .env
nano .env
```

### 3. Configurar serviço systemd

```bash
# Copiar o arquivo de serviço
sudo cp deploy/x1frifas.service /etc/systemd/system/

# Habilitar e iniciar
sudo systemctl daemon-reload
sudo systemctl enable x1frifas
sudo systemctl start x1frifas

# Verificar status
sudo systemctl status x1frifas
```

### 4. Ver logs em tempo real

```bash
sudo journalctl -u x1frifas -f
```

### 5. Atualizar o bot

```bash
cd /opt/x1frifas
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt  # se houve mudança nas dependências
sudo systemctl restart x1frifas
```

---

## 🔐 Variáveis de Ambiente

Copie `.env.example` para `.env` e preencha os valores. Nunca commite o `.env` real no Git.

```env
# ── Discord (obrigatório) ──────────────────────────────────────
DISCORD_TOKEN=seu_token_aqui

# ── MongoDB Atlas (obrigatório) ───────────────────────────────
MONGO_URI=mongodb+srv://<usuario>:<senha>@<cluster>.mongodb.net/<database>?retryWrites=true&w=majority
MONGO_DB_NAME=x1frifas

# ── Efí Pay / PIX — renovação automática (opcional) ──────────
EFI_CLIENT_ID=seu_client_id_efi
EFI_CLIENT_SECRET=seu_client_secret_efi
EFI_PIX_KEY=sua_chave_pix
EFI_SANDBOX=true          # false em produção

# ── Webhook Efí Pay (opcional) ────────────────────────────────
WEBHOOK_BASE_URL=https://meubot.com

# ── Preços de renovação (opcional) ───────────────────────────
RENEWAL_PRICE_7D=10.00
RENEWAL_PRICE_15D=18.00
RENEWAL_PRICE_30D=25.00

# ── Configurações gerais ─────────────────────────────────────
LOG_LEVEL=INFO
SERVER_NAME=X1 Frifas
```

---

## 📁 Estrutura do Projeto

```
X1_frifas-Discord_bot/
├── .env.example                   # Template de variáveis de ambiente
├── .gitignore
├── Dockerfile                     # Imagem Python 3.11-slim
├── railway.toml                   # Configuração de deploy Railway
├── requirements.txt               # Dependências Python
│
├── assets/                        # Banners e imagens dos canais de partida
│
├── deploy/
│   ├── x1frifas.service           # Serviço systemd para VPS
│   ├── RAILWAY.md                 # Guia detalhado de deploy Railway
│   └── MANUTENCAO.md              # Guia de manutenção e operações
│
├── docs/
│   └── COMMANDS.md                # 📖 Referência completa de comandos
│
└── src/
    ├── main.py                    # Entry point — inicialização do bot
    │
    ├── cogs/                      # Comandos organizados por domínio
    │   ├── admin_cog.py           # Setup, moderação, operacional
    │   ├── mediator_cog.py        # Gestão de mediadores e /silence
    │   ├── support_cog.py         # Tickets e canais de suporte
    │   ├── match_cog.py           # Partidas, perfil, análise
    │   ├── analyst_cog.py         # Casos de denúncia e blacklist
    │   ├── invite_cog.py          # Convites e rate limit
    │   ├── influencer_cog.py      # Sistema de influencers
    │   ├── renewal_cog.py         # Renovação de licença via PIX
    │   ├── renewal_dashboard_cog.py # Dashboard de contratos
    │   └── thread_pool_cog.py     # Pool e reutilização de threads
    │
    ├── services/                  # Lógica de negócio
    ├── views/                     # Botões, modais, selects, embeds
    ├── models/                    # Modelos de dados (Pydantic)
    ├── config/                    # Configurações e mapeamento de canais
    └── utils/                     # Logger, retry, datetime, helpers
```

---

## ⚙️ Primeiro Setup do Servidor

Após o bot estar online, execute **uma única vez** em qualquer canal onde você tenha permissão de administrador:

```
!setupcanais
```

Este comando cria e configura:
- ✅ Todos os cargos necessários
- ✅ Todas as categorias e canais
- ✅ Todas as permissões por cargo
- ✅ Todos os painéis e embeds interativos
- ✅ Cards de fila de partida
- ✅ Dashboards de analytics

> **Atenção:** o `!setupcanais` pode ser executado novamente para repostar painéis sem perder dados. Ele não apaga mensagens fora dos painéis.

---

## 👥 Perfis de Usuário

| Cargo | Responsabilidades principais |
|-------|-----------------------------|
| **Controller / ADM** | Setup do servidor, moderação, dashboards, gestão completa |
| **Mediador** | Conduzir partidas, confirmar pagamento, definir vencedor |
| **Suporte** | Atender tickets, abrir/fechar canais de atendimento |
| **Analista** | Analisar denúncias, gerenciar blacklist |
| **Membro / Jogador** | Entrar em filas, abrir tickets, consultar perfil |

> 📖 Para a lista completa de comandos por perfil, acesse [`docs/COMMANDS.md`](docs/COMMANDS.md).

---

## 🔧 Troubleshooting

**Bot não conecta ao banco:**
- Verifique se o IP `0.0.0.0/0` está liberado no MongoDB Atlas → Network Access
- Confirme que `MONGO_URI` não tem espaços extras

**Bot inicia mas cai em loop:**
- Veja os logs — geralmente variável de ambiente ausente
- Confirme que `DISCORD_TOKEN` é válido e o bot tem os intents habilitados no portal do Discord

**Intents necessários no Discord Developer Portal:**
- `Message Content Intent` ✅
- `Server Members Intent` ✅
- `Presence Intent` ✅ (opcional, para AFK check)

**Webhook PIX não funciona:**
- `EFI_SANDBOX` deve ser `false` em produção
- A URL em `WEBHOOK_BASE_URL` deve ser pública (Railway ou VPS com IP)
- Configurar a URL no painel Efí Pay: `https://sua-url.com/webhook/efi`

---

## 🔗 Links Úteis

| Recurso | Link |
|---------|------|
| Discord Developer Portal | [discord.com/developers](https://discord.com/developers/applications) |
| MongoDB Atlas | [cloud.mongodb.com](https://cloud.mongodb.com) |
| Railway | [railway.app](https://railway.app) |
| Efí Pay | [efipay.com.br](https://efipay.com.br) |
| discord.py docs | [discordpy.readthedocs.io](https://discordpy.readthedocs.io) |
| Guia Railway detalhado | [`deploy/RAILWAY.md`](deploy/RAILWAY.md) |
| Guia de manutenção | [`deploy/MANUTENCAO.md`](deploy/MANUTENCAO.md) |
| Referência de comandos | [`docs/COMMANDS.md`](docs/COMMANDS.md) |

---

<div align="center">

Feito com ❤️ para o servidor X1 Frifas

</div>
