import logging
import os
import sys
from typing import Optional
from app.core.config import settings

def setup_logger(name: str = "app") -> logging.Logger:
    logger = logging.getLogger(name)
    
    # If the logger already has handlers, don't duplicate them
    if logger.handlers:
        return logger
        
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Optional File handler
    if settings.log_file:
        try:
            log_dir = os.path.dirname(settings.log_file)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            file_handler = logging.FileHandler(settings.log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Failed to configure file logger for path {settings.log_file}: {str(e)}")
            
    # Prevent propagation to root logger if using custom config
    logger.propagate = False
    
    return logger

# Primary app-wide logger singleton
logger = setup_logger("app")
