class AntiSpamConfig:
    SPAM_BLOCK_ROLE_NAME      = "Bloqueado"
    SPAM_BLOCKED_CHANNEL_NAME = "membros-bloqueados"
    BAN_CONTROL_CATEGORY_NAME = "🚫Ban-Control"

    RATE_WINDOW_SECS    = 10
    RATE_MAX_MESSAGES   = 7
    DUP_WINDOW_SECS     = 25
    DUP_MAX_COUNT       = 4
    MAX_MENTIONS_PER_MESSAGE = 8

    LOG_CHANNEL_FALLBACK_NAME = "📢avisos"
