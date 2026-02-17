# 🎮 X1 Discord Bot - Sistema de Partidas Automático

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)
![Discord.py](https://img.shields.io/badge/discord.py-2.3.2-blue.svg)
![MongoDB](https://img.shields.io/badge/MongoDB-7.0-green.svg)
![Docker](https://img.shields.io/badge/docker-ready-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)

**Bot Discord completo para gerenciamento automático de partidas de Free Fire com sistema de filas, mediadores e apostas.**

[Instalação](#-instalação) •
[Comandos](#-comandos-do-discord) •
[Documentação](#-estrutura-do-projeto) •
[Suporte](#-contato)

<img src="https://img.shields.io/badge/Free%20Fire-FF5733?style=for-the-badge&logo=freefire&logoColor=white" alt="Free Fire"/>

</div>

---

## 📋 Índice

- [Sobre o Projeto](#-sobre-o-projeto)
- [Features](#-features)
- [Demo](#-demo)
- [Tecnologias](#️-tecnologias)
- [Requisitos](#-requisitos)
- [Instalação](#-instalação)
  - [Com Docker (Recomendado)](#-com-docker-recomendado)
  - [Sem Docker](#-sem-docker)
- [Configuração](#️-configuração)
- [Comandos do Discord](#-comandos-do-discord)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Como Usar](#-como-usar)
- [Fluxo de Partida](#-fluxo-de-uma-partida)
- [Troubleshooting](#-troubleshooting)
- [FAQ](#-faq)
- [Roadmap](#-roadmap)
- [Contribuindo](#-contribuindo)
- [Licença](#-licença)
- [Contato](#-contato)

---

## 🎯 Sobre o Projeto

O **X1 Discord Bot** é um sistema automatizado **completo e profissional** para organizar partidas de Free Fire com apostas em servidores Discord.

### 💡 Por que usar este bot?

- 🚀 **Automação Total** - Sem precisar gerenciar filas manualmente
- ⚖️ **Sistema Justo** - Distribuição automática de mediadores
- 💰 **Múltiplos Valores** - R$ 2 a R$ 200
- 🎮 **Todos os Modos** - 1x1, 2x2, 3x3, 4x4
- 📱 **Multiplataforma** - Mobile, Emulador, Misto
- ⏱️ **Confirmação Rápida** - Timer de 60 segundos
- 🔒 **Seguro** - Sistema de verificação de idade integrado

---

## ⚡ Features

<table>
<tr>
<td>

### 🎮 Sistema de Partidas
- ✅ Cards interativos com botões
- ✅ Filas por modo/valor/GEL
- ✅ Confirmação automática
- ✅ Tópicos privados auto-criados
- ✅ Notificações em tempo real

</td>
<td>

### 👨‍⚖️ Sistema de Mediadores
- ✅ Painel exclusivo para mediadores
- ✅ Fila automática e justa
- ✅ Estatísticas detalhadas
- ✅ Notificação via DM
- ✅ Histórico de mediações

</td>
</tr>
<tr>
<td>

### 🔐 Sistema de Verificação
- ✅ Onboarding automático
- ✅ Verificação de idade
- ✅ Atribuição de cargos
- ✅ Mensagens de boas-vindas
- ✅ Anti-spam integrado

</td>
<td>

### 📊 Banco de Dados
- ✅ MongoDB robusto
- ✅ Histórico completo
- ✅ Estatísticas em tempo real
- ✅ Backup automático
- ✅ Performance otimizada

</td>
</tr>
</table>

---

## 🎬 Demo

### 📸 Screenshots

<details>
<summary>🖼️ Clique para ver imagens do bot</summary>

#### Card de Partidas
```
┌────────────────────────────────────┐
│  💰 R$ 10,00                       │
├────────────────────────────────────┤
│ Modo: 1x1 Mobile                   │
│ Jogadores necessários: 2           │
│                                    │
│ 🔥 GEL NORMAL: 0/2 jogadores       │
│ ♾️ GEL INFINITO: 1/2 jogadores     │
│                                    │
│  [🔥 GEL NORMAL]                   │
│  [♾️ GEL INFINITO]                 │
│  [🚪 SAIR DA FILA]                 │
└────────────────────────────────────┘
```

#### Painel de Mediadores
```
┌────────────────────────────────────┐
│  👨‍⚖️ PAINEL DE MEDIADORES          │
├────────────────────────────────────┤
│ Gerencie sua presença na fila     │
│                                    │
│ Mediadores na fila: 5              │
│ Sua posição: 3º                    │
│                                    │
│  [✅ Entrar na Fila]               │
│  [❌ Sair da Fila]                 │
│  [📊 Ver Fila Completa]            │
└────────────────────────────────────┘
```

</details>

---

## 🛠️ Tecnologias

<div align="center">

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Discord](https://img.shields.io/badge/Discord.py-5865F2?style=for-the-badge&logo=discord&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-47A248?style=for-the-badge&logo=mongodb&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![AsyncIO](https://img.shields.io/badge/AsyncIO-3776AB?style=for-the-badge&logo=python&logoColor=white)

</div>

| Tecnologia | Versão | Uso |
|------------|--------|-----|
| **Python** | 3.11+ | Linguagem principal |
| **discord.py** | 2.3.2 | API do Discord |
| **Motor** | 3.3.2 | Driver MongoDB assíncrono |
| **MongoDB** | 7.0 | Banco de dados |
| **Docker** | 20.10+ | Containerização |
| **Docker Compose** | 2.0+ | Orquestração |

---

## 📦 Requisitos

### ✅ Com Docker (Recomendado)

```bash
✓ Docker 20.10+
✓ Docker Compose 2.0+
✓ 2GB RAM
✓ 5GB espaço em disco
✓ Token do Discord Bot
```

### 📋 Sem Docker

```bash
✓ Python 3.11+
✓ MongoDB 7.0+
✓ pip (Python package manager)
✓ 2GB RAM
✓ Token do Discord Bot
```

---

## 🚀 Instalação

### 🐳 Com Docker (Recomendado)

#### Passo 1: Clone o Repositório

```bash
git clone https://github.com/seu-usuario/x1-discord-bot.git
cd x1-discord-bot
```

#### Passo 2: Configure Variáveis de Ambiente

```bash
# Copie o arquivo de exemplo
cp .env.example .env

# Edite com suas credenciais
nano .env
```

**Arquivo `.env`:**
```env
# Discord Bot Token (obrigatório)
DISCORD_BOT_TOKEN=seu_token_aqui

# MongoDB
MONGODB_URI=mongodb://mongodb:27017
DATABASE_NAME=x1_discord_bot

# Bot Config
COMMAND_PREFIX=!
BOT_OWNER_ID=seu_discord_id

# Opcional
LOG_LEVEL=INFO
TIMEZONE=America/Sao_Paulo
```

#### Passo 3: Inicie os Serviços

```bash
# Build e start
docker-compose up -d

# Ver logs
docker-compose logs -f bot

# Verificar status
docker-compose ps
```

**Comandos úteis:**
```bash
# Parar
docker-compose down

# Reiniciar apenas o bot
docker-compose restart bot

# Rebuild completo
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Limpar tudo
docker-compose down -v
```

---

### 💻 Sem Docker

#### Passo 1: Clone e Prepare Ambiente

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/x1-discord-bot.git
cd x1-discord-bot

# Crie ambiente virtual
python3 -m venv venv

# Ative o ambiente
source venv/bin/activate  # Linux/Mac
# ou
venv\\Scripts\\activate  # Windows

# Instale dependências
pip install -r requirements.txt
```

#### Passo 2: Instale e Configure MongoDB

**Ubuntu/Debian:**
```bash
# Instalar MongoDB
wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt-get update
sudo apt-get install -y mongodb-org

# Iniciar serviço
sudo systemctl start mongod
sudo systemctl enable mongod
```

**macOS:**
```bash
# Com Homebrew
brew tap mongodb/brew
brew install mongodb-community@7.0
brew services start mongodb-community@7.0
```

**Windows:**
```powershell
# Baixe e instale de: https://www.mongodb.com/try/download/community
# Inicie o serviço MongoDB
```

#### Passo 3: Configure e Execute

```bash
# Configure .env
cp .env.example .env
nano .env

# Ajuste MONGODB_URI
MONGODB_URI=mongodb://localhost:27017

# Execute o bot
cd src
python main.py
```

---

## ⚙️ Configuração

### 1️⃣ Criar Bot no Discord

<details>
<summary>📖 Guia Completo (clique para expandir)</summary>

1. **Acesse o Portal:**
   - https://discord.com/developers/applications

2. **Crie a Aplicação:**
   - Clique em "New Application"
   - Dê um nome (ex: "X1 Bot")
   - Aceite os termos

3. **Configure o Bot:**
   - Vá em "Bot" no menu lateral
   - Clique em "Add Bot" → "Yes, do it!"
   - **Copie o TOKEN** 🔑 (guarde com segurança!)

4. **Ative Intents Privilegiados:**
   ```
   ✅ PRESENCE INTENT
   ✅ SERVER MEMBERS INTENT  
   ✅ MESSAGE CONTENT INTENT
   ```

5. **Configurações Opcionais:**
   - Icon: Adicione uma imagem legal
   - Username: Nome que aparecerá no Discord
   - Public Bot: Desmarque se quiser privado

</details>

### 2️⃣ Convidar Bot para Servidor

**URL de Convite:**
```
https://discord.com/api/oauth2/authorize?client_id=SEU_CLIENT_ID&permissions=8&scope=bot%20applications.commands
```

> ⚠️ Substitua `SEU_CLIENT_ID` pelo Application ID da aplicação

**Permissões Necessárias:**
- ✅ Administrator (recomendado)

Ou individualmente:
- ✅ Manage Channels
- ✅ Manage Roles  
- ✅ Read Messages/View Channels
- ✅ Send Messages
- ✅ Manage Messages
- ✅ Create Public Threads
- ✅ Send Messages in Threads
- ✅ Embed Links
- ✅ Add Reactions

### 3️⃣ Configurar no Discord

Após bot online, execute no servidor:

```discord
!setupcanais
!setupverificacao #verificacao @Verificado
!setupmediadores
!atualizartodos
```

✅ **Pronto! Bot configurado!**

---

## 📝 Comandos do Discord

### 🔧 Administração

| Comando | Descrição | Exemplo |
|---------|-----------|---------|
| `!setupcanais` | Cria estrutura completa de canais | `!setupcanais` |
| `!setupverificacao` | Configura sistema de verificação | `!setupverificacao #verificacao @Verificado` |
| `!setupmediadores` | Cria painel de mediadores | `!setupmediadores` |
| `!atualizarcards` | Atualiza cards de um canal | `!atualizarcards #1x1-mob` |
| `!atualizartodos` | Atualiza todos os cards | `!atualizartodos` |
| `!fila` | Ver fila de mediadores | `!fila` |

### 👤 Usuário

| Comando | Descrição | Exemplo |
|---------|-----------|---------|
| `!help` | Mostra menu de ajuda | `!help` |
| `!ping` | Verifica latência do bot | `!ping` |
| `!stats` | Estatísticas gerais | `!stats` |

### 🎮 Interações com Botões

**📋 Cards de Partida:**
```
🔥 GEL NORMAL    → Entrar fila GEL normal
♾️ GEL INFINITO  → Entrar fila GEL infinito  
🚪 SAIR DA FILA  → Sair de todas as filas
```

**👨‍⚖️ Painel de Mediadores:**
```
✅ Entrar na Fila       → Começar a mediar
❌ Sair da Fila         → Parar de mediar
📊 Ver Fila Completa    → Listar mediadores
```

**🔐 Verificação:**
```
✅ Verificar  → Confirmar idade 18+
```

---

## 📁 Estrutura do Projeto

```
x1-discord-bot/
│
├── 📂 src/                          # Código fonte
│   ├── 📄 main.py                   # Entry point
│   │
│   ├── 📂 config/                   # Configurações
│   │   ├── database.py              # Setup MongoDB
│   │   └── channels_config.py       # Config canais
│   │
│   ├── 📂 models/                   # Modelos de dados
│   │   ├── match.py                 # Modelo Partida
│   │   ├── mediator.py              # Modelo Mediador
│   │   └── queue.py                 # Modelo Fila
│   │
│   ├── 📂 services/                 # Lógica de negócio
│   │   ├── channel_service.py       # Gerencia canais
│   │   ├── match_service.py         # Gerencia partidas
│   │   ├── match_queue_service.py   # Gerencia filas
│   │   └── mediator_queue.py        # Fila mediadores
│   │
│   ├── 📂 views/                    # Interface Discord
│   │   ├── match_queue_view.py      # Cards filas
│   │   ├── mediator_panel_view.py   # Painel mediadores
│   │   └── verification_view.py     # Sistema verificação
│   │
│   └── 📂 utils/                    # Utilitários
│       └── logger.py                # Sistema logs
│
├── 📄 docker-compose.yml            # Config Docker Compose
├── 📄 Dockerfile                    # Imagem Docker
├── 📄 requirements.txt              # Dependências Python
├── 📄 .env.example                  # Exemplo variáveis
├── 📄 .gitignore                    # Arquivos ignorados
├── 📄 LICENSE                       # Licença MIT
└── 📄 README.md                     # Este arquivo
```

---

## 🎯 Como Usar

### 🎮 Para Jogadores

1. 🚪 **Entre no servidor Discord**
2. ✅ **Faça a verificação** (canal boas-vindas)
3. 🎮 **Escolha um canal** (ex: #1x1-mob)
4. 💰 **Clique no valor** desejado (ex: R$ 10)
5. 🔥 **Escolha o GEL** (Normal ou Infinito)
6. ⏳ **Aguarde a fila encher**
7. ✅ **Confirme** (60 segundos para aceitar)
8. 💬 **Entre no tópico** criado
9. 🎉 **Boa partida!**

### 👨‍⚖️ Para Mediadores

1. 🎖️ **Receba o cargo @Mediador** (admin)
2. 📱 **Acesse #painel-mediadores**
3. ✅ **Clique "Entrar na Fila"**
4. 🔔 **Aguarde notificação** de partida
5. 💬 **Entre no tópico**
6. ⚖️ **Medie a partida**
7. ❌ **Clique "Sair da Fila"** quando terminar

---

## 🔄 Fluxo de uma Partida

```
1️⃣  Jogador 1 clica "🔥 GEL NORMAL" (R$ 10)
    ↓
    Sistema: Fila 1/2 jogadores
    ↓

2️⃣  Jogador 2 clica "🔥 GEL NORMAL" (R$ 10)
    ↓
    Sistema: Fila 2/2 → CHEIA! ✅
    ↓

3️⃣  Timer de confirmação inicia (60s)
    ↓
    Notifica ambos jogadores
    ↓

4️⃣  Jogadores clicam "✅ ACEITAR"
    ↓
    Jogador 1: ✅ Confirmado
    Jogador 2: ✅ Confirmado
    ↓

5️⃣  Sistema busca mediador
    ↓
    Mediador encontrado: @MediadorX
    ↓

6️⃣  Cria tópico privado
    ↓
    Nome: "🔥 R$ 10 | 1X1-MOB | Normal"
    ↓

7️⃣  Adiciona participantes ao tópico
    ↓

8️⃣  Notifica mediador via DM
    ↓

🎮  PARTIDA INICIADA!
```

---

## 🐛 Troubleshooting

<details>
<summary><b>❌ Bot não responde comandos</b></summary>

**Soluções:**
```bash
# Verificar logs
docker-compose logs -f bot

# Verificar status
docker-compose ps

# Reiniciar
docker-compose restart bot
```

</details>

<details>
<summary><b>❌ Erro de conexão MongoDB</b></summary>

```bash
# Status do MongoDB
docker-compose ps mongodb

# Logs
docker-compose logs -f mongodb

# Reiniciar
docker-compose restart mongodb
```

</details>

<details>
<summary><b>❌ Bot não cria canais/cargos</b></summary>

- Verifique se o bot tem permissão de **Administrator**
- Ou dê as permissões específicas manualmente

</details>

---

## ❓ FAQ

<details>
<summary><b>Posso usar em múltiplos servidores?</b></summary>

Sim! O bot suporta múltiplos servidores. Cada servidor terá suas próprias configurações e filas independentes.

</details>

<details>
<summary><b>Como adicionar mais valores de aposta?</b></summary>

Edite `src/config/channels_config.py`:

```python
BET_VALUES = [2.00, 5.00, 10.00, 20.00, 50.00, 100.00, 200.00, 500.00]
```

Depois rode: `!atualizartodos`

</details>

<details>
<summary><b>Como fazer backup do banco de dados?</b></summary>

```bash
# Backup
docker exec x1_mongodb mongodump --out /backup

# Copiar para host
docker cp x1_mongodb:/backup ./backup_$(date +%Y%m%d)

# Restaurar
docker exec x1_mongodb mongorestore /backup
```

</details>

---

## 🗺️ Roadmap

### 🚀 Versão 2.0 (Futuro)

- [ ] 🎨 Dashboard web para administração
- [ ] 📊 Sistema de ranking de jogadores
- [ ] 💎 Sistema de níveis e XP
- [ ] 🏆 Torneios automatizados
- [ ] 💳 Integração com pagamentos
- [ ] 📱 Comandos slash (/)
- [ ] 🌐 Suporte multi-idioma
- [ ] 📈 Estatísticas avançadas

---

## 🤝 Contribuindo

Contribuições são **muito bem-vindas**! 🎉

1. 🍴 **Fork** o projeto
2. 🌿 **Crie uma branch** (`git checkout -b feature/MinhaFeature`)
3. ✏️ **Commit** suas mudanças (`git commit -m 'feat: Adiciona MinhaFeature'`)
4. 📤 **Push** para a branch (`git push origin feature/MinhaFeature`)
5. 🔃 **Abra um Pull Request**

---

## 📄 Licença

Este projeto está sob a licença **MIT**.

```
MIT License

Copyright (c) 2026 Seu Nome

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

<div align="center">

**Alvaro Sáteles** - Dev
**Victor Jesus** - Dev
**Arthur Paiva** - Dev
**Eduardo Reis** - Dono







