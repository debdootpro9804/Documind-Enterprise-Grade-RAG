import sys
from loguru import logger


def setup_logging(log_level: str = "INFO") -> None:
    logger.remove()  # Remove default handler

    # Console — human readable in dev
    logger.add(
        sys.stdout,
        level=log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # File — JSON structured for production parsing
    logger.add(
        "logs/app.log",
        level="INFO",
        format="{time} | {level} | {name}:{line} | {message}",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        serialize=True,  # outputs JSON
    )

    logger.info("Logging initialised")