# X1 Free Fire Discord Bot 🎮

Sistema completo para gerenciamento de partidas X1 Free Fire em Discord com arquitetura escalável.

## 🚀 Features

- ✅ Bot Discord com discord.py v2
- ✅ API REST com FastAPI
- ✅ Database MongoDB com Motor (async)
- ✅ Logging estruturado e auditoria
- ✅ Docker & Docker Compose
- ✅ CI/CD com GitHub Actions
- ✅ Estrutura profissional e modular

## 📋 Pré-requisitos

- Python 3.11+
- Docker & Docker Compose
- Git
- Discord Bot Token
- MongoDB Atlas (ou local)

## 🔧 Setup Inicial

### 1. Clone o Repositório

```bash
git clone https://github.com/seu-usuario/x1-discord-bot.git
cd x1-discord-bot
```

### 2. Configure Variáveis de Ambiente

```bash
cp .env.example .env
# Edite .env com suas credenciais
```

### 3. Inicie com Docker

```bash
docker-compose up -d
```

### 4. Verifique Status

```bash
# Ver logs do bot
docker-compose logs -f bot

# Ver logs da API
docker-compose logs -f api

# Ver logs do MongoDB
docker-compose logs -f mongodb
```

## 📦 Instalação Local (sem Docker)

```bash
# Crie ambiente virtual
python -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate

# Instale dependências
pip install -r requirements.txt

# Configure .env
cp .env.example .env

# Execute (com MongoDB rodando localmente)
python -m src.bot.main
```

## 📁 Estrutura do Projeto

```
src/
├── bot/              # Discord Bot
│   ├── main.py
│   ├── config.py
│   └── cogs/         # Comandos
├── api/              # FastAPI
│   └── main.py
├── database/         # MongoDB
│   └── mongodb.py
├── services/         # Lógica de negócio
├── utils/            # Utilitários
└── discord_components/  # UI Discord
```

## 🐳 Comandos Docker Úteis

```bash
# Inicia containers
docker-compose up -d

# Para containers
docker-compose down

# Rebuild após mudanças
docker-compose up -d --build

# Limpar volumes
docker-compose down -v

# Ver logs em tempo real
docker-compose logs -f [service]

# Executar comando em container
docker-compose exec bot bash
```

## 📡 API Endpoints

- `GET /health` - Status da API
- `GET /matches` - Listar partidas
- `POST /matches` - Criar partida
- `GET /players` - Listar jogadores
- `GET /mediadores` - Listar mediadores

*Veja `/docs` para documentação interativa (FastAPI Swagger)*

## 🧪 Testes

```bash
# Executar testes
pytest tests/ -v

# Com cobertura
pytest tests/ --cov=src

# Watch mode
pytest-watch
```

## 🔗 Git Workflow

```bash
# Feature branch
git checkout -b feature/victor
git pull origin main
git branch
git add .
git commit -m "subindo alterações victor"
git push origin feature/victor

# Pull request → merge → CI/CD automático
```

## 📊 Monitoramento

- **Logs**: `logs/bot.log`
- **API Docs**: `http://localhost:8000/docs`
- **MongoDB Admin**: `mongodb://localhost:27017`

## 🚨 Troubleshooting

### Bot não conecta
```bash
# Verifique token no .env
docker-compose logs bot | grep ERROR
```

### MongoDB Connection Error
```bash
# Verifique se MongoDB está rodando
docker-compose logs mongodb

# Reinicie
docker-compose restart mongodb
```

### Porta em uso
```bash
# Mude a porta em docker-compose.yml
# ou
lsof -i :8000  # Encontrar processo
kill -9 <PID>  # Matar processo
```

## 🤝 Contribuindo
1. Fork o repositório
2. Crie uma branch (`git checkout -b feature/AmazingFeature`)
3. Commit mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📝 Licença

Este projeto está licenciado sob a MIT License - veja o arquivo LICENSE.

