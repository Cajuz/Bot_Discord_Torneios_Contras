import logging
import os
from logging.handlers import TimedRotatingFileHandler
from typing import Any


class ColoredFormatter(logging.Formatter):
    """Formatter personalizado com cores ANSI para console."""

    COLORS = {
        'DEBUG':    '\033[36m',   # Cyan
        'INFO':     '\033[34m',   # Blue
        'WARNING':  '\033[33m',   # Yellow
        'ERROR':    '\033[31m',   # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        record = logging.makeLogRecord(record.__dict__)  # cópia p/ não mutar o original
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logger(name: str = "SolarBot") -> logging.Logger:
    """Configura e retorna o logger global.

    - Console: colorido, nível DEBUG
    - Arquivo: logs/bot.log com rotação diária (7 dias de histórico)
    - propagate=False para evitar duplicação com o root logger
    """
    logger = logging.getLogger(name)

    # Evita adicionar handlers duplicados em imports múltiplos
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # FIX: evita duplicação com root logger / discord.py

    fmt = '%(asctime)s [%(levelname)s] %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'

    # ── Handler de console (colorido) ────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(ColoredFormatter(fmt, datefmt=datefmt))
    logger.addHandler(console_handler)

    # ── Handler de arquivo com rotação diária ────────────────────────────
    # Cria a pasta logs/ se não existir (relativo ao cwd, que é src/)
    log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'bot.log')

    file_handler = TimedRotatingFileHandler(
        filename=log_path,
        when='midnight',      # Rotação diária à meia-noite
        interval=1,
        backupCount=7,        # Mantém 7 dias de histórico
        encoding='utf-8',
        utc=True,
    )
    file_handler.setLevel(logging.INFO)  # Arquivo só guarda INFO+, DEBUG fica no console
    file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    logger.addHandler(file_handler)

    return logger


# Logger global — importado por todo o projeto
logger = setup_logger()


def log_success(message: str, data: Any = None) -> None:
    """Log de sucesso (INFO com prefixo ✅)."""
    logger.info(f"✅ {message}")
    if data:
        logger.debug(f"   Data: {data}")
