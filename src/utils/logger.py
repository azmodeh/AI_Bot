import logging
import sys
from pathlib import Path


def configure_logging():
    """Configure logging for the bot"""
    
    # Get project root (parent of src directory)
    project_root = Path(__file__).parent.parent.parent.absolute()
    log_dir = project_root / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "bot.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logging.getLogger("telethon").setLevel(logging.WARNING)
