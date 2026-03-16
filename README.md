# X1 Frifas — Discord Bot

Bot de gestão de partidas de Free Fire com apostas, mediação, suporte, análise de denúncias, renovação de licença via PIX, sistema de convites, influencers e reutilização de tópicos.

---

## Visão geral

O X1 Frifas é um bot modular para servidores Discord focados em organização de partidas mediadas.  
Ele centraliza o fluxo de filas, criação de partidas, confirmação de pagamento, definição de vencedor, entrega de prêmio, suporte ao usuário, análise de denúncias e operação administrativa.

---

## Estrutura

```bash
src/
├── main.py                     # Entry point do bot
├── cogs/                       # Comandos por domínio
│   ├── admin_cog.py            # Comandos administrativos e setup
│   ├── mediator_cog.py         # Gestão de mediadores e /silence
│   ├── support_cog.py          # Chamados e canais privados de suporte
│   ├── match_cog.py            # Partidas, perfil e solicitação de análise
│   ├── analyst_cog.py          # Casos de análise e blacklist
│   ├── invite_cog.py           # Convites e rate limit stats
│   ├── influencer_cog.py       # Gestão de influencers
│   ├── renewal_cog.py          # Renovação de licença via PIX
│   └── thread_pool_cog.py      # Monitoramento e pré-aquecimento do pool de threads
├── services/                   # Lógica de negócio
│   ├── match_service.py
│   ├── thread_reuse_service.py
│   ├── mediator_queue.py
│   ├── invite_tracker_service.py
│   ├── rate_limit_monitor_service.py
│   ├── health_check_service.py
│   ├── influencer_service.py
│   ├── anti_spam_service.py
│   ├── onboarding_service.py
│   └── ...
├── views/                      # Botões, modais, selects e embeds
├── models/                     # Modelos de dados
├── config/                     # Configurações gerais e canais
└── utils/                      # Logger, retry, datetime, helpers
deploy/
├── x1frifas.service            # Serviço systemd para VPS
└── INSTALL.md                  # Guia de instalação
Instalação
bash
# 1. Clone o repositório
git clone https://github.com/Cajuz/X1_frifas-Discord_bot.git
cd X1_frifas-Discord_bot

# 2. Crie o arquivo .env
cp .env.example .env

# 3. Preencha as variáveis necessárias
# DISCORD_TOKEN=
# MONGO_URI=
# EFI_CLIENT_ID=
# EFI_CLIENT_SECRET=
# WEBHOOK_BASE_URL=
# API_PORT=8000
# e demais configurações do projeto

# 4. Instale as dependências
pip install -r requirements.txt

# 5. Execute o bot
python src/main.py
Docker
bash
docker-compose up -d
VPS com systemd
bash
sudo cp deploy/x1frifas.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable x1frifas
sudo systemctl start x1frifas
sudo journalctl -u x1frifas -f
Perfis de uso
ADM
Responsável pela configuração do servidor, dashboards, canais, moderação, monitoramento técnico, gestão de mediadores, influencers e pool de threads.

Mediador
Responsável por conduzir a partida dentro do tópico, confirmar pagamento, iniciar a partida, declarar vencedor, confirmar envio do prêmio e aplicar silêncio em canal/thread.

Suporte
Responsável por atendimento em canais privados, fechamento e conclusão de chamados.

Analista
Responsável por assumir casos de denúncia, decidir casos e gerenciar a blacklist.

Jogador
Pode entrar em filas, cancelar entrada, consultar perfil, abrir chamados, solicitar análise e confirmar recebimento do prêmio.

Comandos principais
Administrador
Comando	Tipo	Descrição
!setupcanais	Prefixo	Configura a estrutura principal do servidor
!setupfaturamento	Prefixo	Posta o painel de faturamento
!setupguias	Prefixo	Atualiza canais de guias
!setupsuporte	Prefixo	Posta os painéis de suporte
!setupmediador	Prefixo	Posta os painéis de mediador
!setupquerosermediador	Prefixo	Posta painel de candidatura a mediador
!setupinfluencers	Prefixo	Posta painéis de influencers
!setuppix	Prefixo	Posta painel de PIX
!setuprenovacao	Prefixo	Posta painel de renovação
!setuppartidas	Prefixo	Posta os cards de fila de partida
!setupdashboards	Prefixo	Atualiza dashboards
!dashboard	Prefixo	Atualiza o dashboard principal
!atualizardashboards	Prefixo	Atualiza todos os dashboards
!healthcheck	Prefixo	Exibe painel técnico do bot
!bloquear @membro [motivo]	Prefixo	Bloqueia membro manualmente
!desbloquear @membro	Prefixo	Remove bloqueio manual
!limpar [1-100]	Prefixo	Limpa mensagens do canal
!verpix [@membro]	Prefixo	Consulta chave PIX cadastrada
!helpadm	Prefixo	Lista comandos administrativos
!addmediador @membro	Prefixo	Adiciona membro à fila de mediadores
!removemediador @membro	Prefixo	Remove membro da fila de mediadores
!fila	Prefixo	Exibe fila e status de mediadores
!setupanalise	Prefixo	Posta painel de solicitação de análise
!setupexposed	Prefixo	Posta painel da blacklist
!criarcanalsuporte [@membro]	Prefixo	Cria canal privado de suporte
!renovarmediador @membro [dias] [valor]	Prefixo	Gera cobrança PIX manual para renovação
/threadpool setup	Slash	Posta ou atualiza o painel do pool de threads
/threadpool preaquecer [quantidade]	Slash	Cria threads arquivadas no pool
/threadpool status	Slash	Mostra o resumo do estado do pool
/topconvites	Slash	Ranking de convites
/ratelimitstats [horas]	Slash	Estatísticas de rate limit
/influencer add @membro invitecode [comissao]	Slash	Cadastra influencer
/influencer remove @membro	Slash	Remove influencer
/influencer ranking	Slash	Ranking de influencers
Mediador
Os comandos de fluxo da partida devem ser usados dentro da thread da partida.

Comando	Tipo	Descrição
!menu_partida	Prefixo	Envia painel do mediador via DM
!confirmar_pagamento	Prefixo	Confirma recebimento dos pagamentos
!iniciar_partida	Prefixo	Inicia a partida
!winner_team blue	Prefixo	Define Time Blue como vencedor
!winner_team red	Prefixo	Define Time Red como vencedor
!prize	Prefixo	Confirma que o prêmio foi enviado
!cancelar_match [motivo]	Prefixo	Cancela a partida
/silence @membro [segundos] [motivo]	Slash	Silencia jogador no canal/thread atual
/renovar [dias]	Slash	Gera cobrança PIX para renovar licença
!verpix [@membro]	Prefixo	Consulta chave PIX
Suporte
Comando	Tipo	Descrição
!chamado	Prefixo	Lista chamados abertos do usuário
!fecharchamado [ticket_id]	Prefixo	Fecha um chamado
!concluirchamado [ticket_id]	Prefixo	Marca chamado como resolvido
!criarcanalsuporte [@membro]	Prefixo	Cria canal privado de suporte
/renomearcanal [sufixo]	Slash	Renomeia o canal do agente de suporte
!help	Prefixo	Lista comandos gerais úteis
Analista
Comando	Tipo	Descrição
/assumircaso [case_id]	Slash	Assume um caso de análise
/decidircaso [case_id] [decisao] [motivo]	Slash	Encerra um caso de análise
/blacklistadd [player_id] [motivo]	Slash	Adiciona jogador à blacklist
/blacklistremove [player_id]	Slash	Remove jogador da blacklist
/blacklistcheck [player_id]	Slash	Consulta blacklist
/blacklistlist	Slash	Lista os últimos registros da blacklist
Decisões possíveis no comando /decidircaso:

confirmado

inconclusivo

invalido

Jogador
Comando	Tipo	Descrição
Botões de fila	UI	Entrar ou sair da fila pelos cards
!cancelar	Prefixo	Cancela sua entrada na fila
/perfil	Slash	Exibe estatísticas de partidas
/convites [@membro]	Slash	Consulta convites
/solicitaranalise [match_id] [motivo] [evidencia]	Slash	Solicita análise de suspeita de hack
!chamado	Prefixo	Lista chamados abertos
!fecharchamado [ticket_id]	Prefixo	Fecha o próprio chamado
Botão Confirmar Recebimento do Prêmio	UI	Confirma que recebeu o prêmio
Fluxo de partida
O jogador entra na fila pelo card no canal.

Quando a fila completa, é criado um tópico de confirmação.

A fila é convertida em partida com mediador.

O mediador confirma pagamento com !confirmar_pagamento.

O mediador inicia com !iniciar_partida.

Ao final, o mediador define o vencedor com !winner_team.

O mediador confirma envio do prêmio com !prize.

O vencedor confirma recebimento pelo botão.

A partida é finalizada e o tópico pode ser devolvido ao pool de reutilização.

Sistema de reutilização de tópicos
O projeto possui um sistema de reutilização de threads para reduzir criação excessiva de tópicos e evitar chegar ao limite operacional do Discord.

Recursos
Reaproveitamento de threads arquivadas

Pré-aquecimento de pool por canal

Monitoramento por painel administrativo

Limpeza e retorno da thread ao pool ao final da partida

Controle de threads ativas e margem de segurança

Comandos
/threadpool setup

/threadpool preaquecer

/threadpool status

Renovação de licença de mediador
A renovação é feita via PIX, com suporte a geração de cobrança, QR Code em DM, validação manual por botão e confirmação automática por webhook.

Recursos
Planos de 7, 15 e 30 dias

Expiração automática da cobrança

Restauração automática do cargo de mediador após pagamento

Avisos de vencimento

Remoção automática do cargo quando a licença expira

Comandos
/renovar

!renovarmediador

Influencers
O sistema de influencers permite cadastrar usuários com código de convite e acompanhar a performance deles.

Recursos
Registro de influencer

Associação com código de convite

Comissão por membro convidado

Ranking e faturamento individual

Comandos
/influencer add

/influencer remove

/influencer stats

/influencer faturamento

/influencer ranking

Convites e rate limit
O bot monitora convites e também registra eventos de rate limit.

Comandos
/convites

/topconvites

/ratelimitstats

Blacklist e análises
O módulo de análise permite denunciar suspeita de hack e encaminhar o caso para analistas.

Recursos
Solicitação de análise por jogador

Fila de casos

Assunção de caso por analista

Decisão final com justificativa

Integração com blacklist

Painel no canal de exposed

Comandos
/solicitaranalise

/assumircaso

/decidircaso

/blacklistadd

/blacklistremove

/blacklistcheck

/blacklistlist

Suporte
O sistema de suporte usa tickets e canais privados por atendente.

Recursos
Abertura de ticket por painel

Fechamento e conclusão de chamado

Canal privado por agente

Renomeação do canal conforme assunto

Comandos
!chamado

!fecharchamado

!concluirchamado

!criarcanalsuporte

/renomearcanal

Variáveis de ambiente
Use o arquivo .env.example como referência.
As variáveis podem incluir, entre outras:

text
DISCORD_TOKEN=
MONGO_URI=
EFI_CLIENT_ID=
EFI_CLIENT_SECRET=
WEBHOOK_BASE_URL=
API_PORT=8000
RENEWAL_PRICE_7D=
RENEWAL_PRICE_15D=
RENEWAL_PRICE_30D=
Features implementadas
Sistema modular com cogs por domínio

Views persistentes registradas no startup

Filas de partida com cards interativos

Gestão completa de partidas mediadas

Confirmação de prêmio por botão

Reutilização de threads

Health check e monitoramento do pool

Sistema de suporte com canais privados

Solicitação de análise de suspeita de hack

Blacklist com painel dedicado

Invite tracker

Rate limit monitor

Influencer control

Renovação automática de licença via PIX

AFK check para fila e partida

Dashboards operacionais

Integração com MongoDB

Deploy em VPS com systemd

Observações
Alguns comandos funcionam apenas em canais específicos, como casos de blacklist no canal exposed.

Os comandos de partida com prefixo devem ser executados dentro da thread da partida.

O comando /silence deve ser usado no canal ou thread em que o membro será silenciado.

A renovação depende da configuração correta da integração PIX e do webhook.
