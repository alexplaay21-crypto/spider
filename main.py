import asyncio
import logging
from pathlib import Path

from config.settings import settings
from core.app import run

Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("logs/core.log", encoding="utf-8")],
)

if __name__ == "__main__":
    asyncio.run(run())
