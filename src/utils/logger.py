import logging
from datetime import datetime
from typing import Any

class ColoredFormatter(logging.Formatter):
    """Formatter personalizado com cores"""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[34m',     # Blue
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'SUCCESS': '\033[32m'   # Green
    }
    RESET = '\033[0m'
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)

def setup_logger(name: str = "MediatorSystem") -> logging.Logger:
    """Configurar logger com cores"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Handler para console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    
    # Formato
    formatter = ColoredFormatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    return logger

# Logger global
logger = setup_logger()

def log_success(message: str, data: Any = None):
    """Log de sucesso customizado"""
    logger.info(f"✅ {message}")
    if data:
        logger.debug(f"   Data: {data}")
