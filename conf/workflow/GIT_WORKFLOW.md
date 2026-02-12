# Guia de Comandos e Workflows Git

## 📝 Commits Convencionais

```bash
# Feature
git commit -m "feat: adiciona comando de fila de partidas"

# Bug fix
git commit -m "fix: corrige validação de jogadores"

# Documentation
git commit -m "docs: atualiza README com instruções Docker"

# Refatoração
git commit -m "refactor: reorganiza estrutura de services"

# Tests
git commit -m "test: adiciona testes para match_service"

# Performance
git commit -m "perf: otimiza query de MongoDB"
```

## 🔄 Workflow Git

### Desenvolvimento em Feature

```bash
# 1. Update da branch main/develop
git checkout develop
git pull origin develop

# 2. Cria feature branch
git checkout -b feature/nova-funcionalidade

# 3. Faz alterações e commits
git add src/
git commit -m "feat: implementa nova funcionalidade"

# 4. Push e Pull Request
git push origin feature/nova-funcionalidade

# Depois de merge, delete local
git checkout develop
git pull origin develop
git branch -d feature/nova-funcionalidade
```

### Bug Fix Hotfix

```bash
# 1. Cria hotfix branch a partir de main
git checkout main
git pull origin main
git checkout -b hotfix/nome-do-bug

# 2. Faz fix
git commit -m "fix: corrige bug crítico"

# 3. Merge em main e develop
git push origin hotfix/nome-do-bug
# (PR em main, depois merge em develop)
```

## 🐳 Docker - Workflow Diário

```bash
# Iniciar ambiente
docker-compose up -d

# Ver status
docker-compose ps

# Ver logs (específico)
docker-compose logs -f bot

# Rebuild após mudanças no Dockerfile
docker-compose up -d --build

# Acessar container
docker-compose exec bot bash

# Parar tudo
docker-compose down

# Remover volumes (⚠️ deleta dados!)
docker-compose down -v

# Limpar imagens não usadas
docker image prune -a
```

## 🔑 Variáveis de Ambiente

Crie um arquivo `.env` na raiz (nunca faça commit!):

```bash
# .env (gitignored)
DISCORD_TOKEN=SEU_TOKEN_AQUI
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/db
ENVIRONMENT=development
```

## 🚀 Deploy com Docker

### Build local para testes

```bash
# Build apenas
docker build -t x1-bot:latest .

# Run container
docker run -e DISCORD_TOKEN=seu_token -e MONGO_URI=sua_uri x1-bot:latest

# Com volumes para logs
docker run -v $(pwd)/logs:/app/logs x1-bot:latest
```

### Push para Docker Hub

```bash
# Login
docker login

# Tag
docker tag x1-bot:latest seu-usuario/x1-bot:latest

# Push
docker push seu-usuario/x1-bot:latest

# Produção pode puxar
docker pull seu-usuario/x1-bot:latest
```

## 📊 Estrutura Sugerida de Branches

```
main (produção - protegida)
  ↑
  ├─ hotfix/* (bugs críticos)
  
develop (staging)
  ↑
  ├─ feature/* (novas features)
  ├─ bugfix/* (correções)
  └─ refactor/* (refatorações)
```

## ✅ Checklist Antes de Push

- [ ] Código testado localmente
- [ ] `flake8` sem erros: `flake8 src`
- [ ] Testes passando: `pytest tests/`
- [ ] Variáveis sensíveis no `.env` (não no código)
- [ ] Commit message descritiva
- [ ] Branch atualizada com upstream: `git pull origin develop`

## 🧪 Testes Antes de Merge

```bash
# Testes unitários
pytest tests/ -v

# Com cobertura
pytest tests/ --cov=src --cov-report=html

# Específico
pytest tests/test_bot.py::test_function -v
```

## 📦 Release (Quando pronto para produção)

```bash
# 1. Update version em setup.py ou package.json
# 2. Merge develop → main
git checkout main
git pull origin main
git merge develop

# 3. Tag release
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin main --tags

# 4. Docker Hub push
docker build -t seu-usuario/x1-bot:1.0.0 .
docker push seu-usuario/x1-bot:1.0.0
```

## 🔍 GitHub Actions CI/CD

Fluxo automático:

1. **Push → GitHub** 
2. **Trigger CI/CD** (`.github/workflows/ci-cd.yml`)
3. **Tests rodando** (pytest, flake8)
4. **Build Docker** (se passou)
5. **Push para Docker Hub** (se na main)
6. **Deploy** (se ativado)

Monitore em: `Actions` tab do GitHub

---

**Última atualização**: Feb 2026
