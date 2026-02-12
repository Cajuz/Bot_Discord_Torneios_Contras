# Docker
docker-compose up -d              # Inicia tudo
docker-compose logs -f bot        # Ver logs do bot
docker-compose down               # Para tudo
docker-compose exec bot bash      # Acessa container

# Git
git status                        # Ver status
git add .                         # Adiciona tudo
git commit -m "mensagem"          # Commit
git push origin main              # Envia para GitHub
git pull origin main              # Puxa do GitHub

# Python (local, sem Docker)
pip install -r requirements.txt   # Instala dependências
pytest tests/                     # Roda testes
flake8 src/                       # Lint
black src/                        # Formata código


