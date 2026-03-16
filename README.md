# X1 Frifas — Discord Bot

Bot de gestão de partidas Free Fire com apostas, mediadores, suporte, analistas e influencers.

## Estrutura

```
src/
├── main.py                  # Entry point
├── cogs/                    # Comandos por domínio
│   ├── admin_cog.py         # Comandos admin
│   ├── mediator_cog.py      # /silence, fila
│   ├── support_cog.py       # Suporte, canais privados
│   ├── match_cog.py         # Partidas, /perfil, /solicitar_analise
│   ├── analyst_cog.py       # Blacklist, #exposed, análise de casos
│   ├── invite_cog.py        # Invite tracker, rate limit monitor
│   ├── influencer_cog.py    # /influencer add/remove/stats/ranking
│   └── renewal_cog.py       # /renovar — PIX Efí Pay
├── services/                # Lógica de negócio
│   ├── afk_service.py       # AFK check (fila + partida)
│   ├── efi_pay_service.py   # Integração Efí Pay / Gerencianet
│   ├── influencer_service.py
│   └── ...
├── views/                   # UI Discord (botões, selects, embeds)
├── models/                  # Modelos de dados
├── config/                  # Configurações e channels config
└── utils/                   # logger, datetime_utils, retry
deploy/
├── x1frifas.service         # Systemd service (VPS)
└── INSTALL.md               # Guia de instalação
```

## Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/Cajuz/X1_frifas-Discord_bot
cd X1_frifas-Discord_bot

# 2. Crie o .env a partir do template
cp .env.example .env
# Preencha DISCORD_TOKEN, MONGO_URI, EFI_CLIENT_ID, etc.

# 3. Instale dependências
pip install -r requirements.txt

# 4. Rode o bot
python src/main.py
```

## Docker

```bash
docker-compose up -d
```

## VPS com systemd

```bash
sudo cp deploy/x1frifas.service /etc/systemd/system/
sudo systemctl enable x1frifas
sudo systemctl start x1frifas
sudo journalctl -u x1frifas -f  # logs em tempo real
```

## Comandos principais

| Comando | Quem pode usar | Descrição |
|---|---|---|
| `!setupcanais` | Admin | Configura todos os canais e cargos |
| `!setup_guias` | Admin | Posta documentação nos canais guia |
| `!setup_mediador` | Admin | Envia painel de mediadores |
| `!setup_suporte` | Admin | Envia painel de suporte |
| `/silence @membro Xs` | Controller | Silencia jogador na thread |
| `/solicitar_analise` | Membro | Abre caso de suspeita de hack |
| `/blacklist_add` | Analyst | Adiciona à blacklist (#exposed) |
| `/renovar` | Controller | Gera QR Code PIX para renovação |
| `/influencer add` | Admin | Cadastra influencer |
| `/influencer stats` | Admin/Influencer | Estatísticas do influencer |
| `/perfil` | Todos | Stats de partidas do usuário |
| `!dashboard` | Admin | Atualiza dashboard de partidas |
| `!healthcheck` | Admin | Status técnico do bot |

## Variáveis de ambiente

Ver `.env.example` para lista completa com descrições.

## Features implementadas

- **R1–R9** Refatoração completa (Cogs, datetime corrigido, retry, views persistentes)
- **F1** Invite Tracker com log no #convites
- **F2** Rate Limit Monitor no #rate-limit-logs
- **F3** Canal #exposed + Blacklist (Analyst + Admin)
- **F4** Canais guia com documentação automática
- **F5** Suporte via Select Menu + Button
- **F6** Canal privado por agente de suporte
- **F7** "Ver Fila" restrito a Admin
- **F8** /silence para mediadores
- **F9** Nomes de thread: confirmar → pagamento → pagar
- **F10** Tema visual #FFD54F/#FFA726
- **F11** Influencer Control com rastreamento e comissão
- **F12** Analytics & Dashboards
- **F13** Renovação automática via PIX Efí Pay (webhook + botão manual)
- **F14** Solicitação de análise de partida para analistas
- **F15** AFK Check: fila (5min) + partida (5min + substituição)
- **E1–E6** Cargos, canais extras, boas-vindas, systemd
