import sys
from loguru import logger

logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{line} — {message}", level="INFO", serialize=False)
logger.add("logs/ethioqs.log", rotation="10 MB", retention="30 days", level="DEBUG", serialize=True)
