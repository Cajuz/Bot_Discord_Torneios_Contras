# Deploy no Railway — Guia Completo

## Pré-requisitos

- Conta no Railway: https://railway.app
- Conta no GitHub com o código do bot
- Conta no MongoDB Atlas (banco de dados gratuito): https://cloud.mongodb.com

---

## Passo 1 — Configurar MongoDB Atlas (banco gratuito)

1. Acesse https://cloud.mongodb.com e crie uma conta
2. Crie um cluster gratuito (M0 Free Tier)
3. Em **Database Access** → crie um usuário com senha
4. Em **Network Access** → clique em **Add IP Address** → **Allow Access from Anywhere** (0.0.0.0/0)
5. Em **Clusters** → clique em **Connect** → **Connect your application**
6. Copie a URI no formato:
   ```
   mongodb+srv://<usuario>:<senha>@<cluster>.mongodb.net/x1frifas?retryWrites=true&w=majority
   ```
   Guarde essa URI para usar no Railway.

---

## Passo 2 — Subir o código no GitHub

```bash
# No seu PC, dentro da pasta do projeto:
git init
git add .
git commit -m "primeiro commit"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/x1frifas-bot.git
git push -u origin main
```

Se o repositório já existe, só dê:
```bash
git add .
git commit -m "atualização"
git push
```

---

## Passo 3 — Criar projeto no Railway

1. Acesse https://railway.app e faça login com GitHub
2. Clique em **New Project**
3. Selecione **Deploy from GitHub repo**
4. Selecione o repositório do bot
5. Railway vai detectar o `Dockerfile` automaticamente

---

## Passo 4 — Configurar as variáveis de ambiente

No Railway, dentro do seu projeto:

1. Clique no serviço criado
2. Vá em **Variables**
3. Adicione cada variável abaixo clicando em **New Variable**:

```
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

> O `WEBHOOK_BASE_URL` será a URL pública gerada pelo Railway.
> Para encontrá-la: vá em **Settings** → **Domains** → copie a URL gerada.

---

## Passo 5 — Deploy

Após adicionar as variáveis:

1. Vá em **Deployments**
2. Clique em **Deploy** (ou o Railway já inicia automaticamente)
3. Aguarde o build (~2 minutos)
4. Veja os logs em tempo real na aba **Logs**

Quando aparecer:
```
✅ MongoDB conectado!
✅ Bot online: X1Frifas#0000
✅ Bot totalmente inicializado!
```
O bot está no ar.

---

## Passo 6 — Configurar domínio público (para webhook Efí Pay)

1. No Railway, vá em **Settings** → **Networking**
2. Clique em **Generate Domain**
3. Copie a URL gerada (ex: `x1frifas-bot.up.railway.app`)
4. Atualize a variável `WEBHOOK_BASE_URL` com essa URL
5. No painel da Efí Pay, configure o webhook para:
   ```
   https://x1frifas-bot.up.railway.app/webhook/efi
   ```

---

## Deploy automático (CI/CD)

A cada `git push` na branch `main`, o Railway faz deploy automático.

```bash
# Atualizar o bot:
git add .
git commit -m "minha atualização"
git push
# Railway detecta e redeploy automaticamente em ~1 min
```

---

## Ver logs em tempo real

No painel do Railway:
- Clique no serviço → aba **Logs**

Ou via CLI:
```bash
npm install -g @railway/cli
railway login
railway logs
```

---

## Preços Railway

| Plano | Custo | Limite |
|-------|-------|--------|
| Trial | Grátis | $5 de crédito (expira) |
| Hobby | $5/mês | $5 de uso incluído, paga o excedente |
| Pro   | $20/mês | Sem limite de uso |

Para um bot Discord médio, o plano **Hobby ($5/mês)** é suficiente.
O consumo típico fica em torno de $2–4/mês de uso real.

---

## Troubleshooting

**Bot não conecta ao banco:**
- Verifique se o IP `0.0.0.0/0` está liberado no MongoDB Atlas
- Confirme a URI no Railway (sem espaços extras)

**Bot inicia mas cai em loop:**
- Veja os logs — provavelmente variável de ambiente faltando
- Confirme que `DISCORD_TOKEN` está correto

**Webhook não recebe pagamentos:**
- Confirme que o domínio foi gerado no Railway
- Verifique a URL no painel da Efí Pay (deve terminar em `/webhook/efi`)
- `EFI_SANDBOX` deve ser `false` em produção

**Redeploy manual:**
- No painel: Deployments → clique nos 3 pontos → **Redeploy**
