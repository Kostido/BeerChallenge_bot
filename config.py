import os
import logging
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Bot token from environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Group chat ID for sharing beer submissions
GROUP_CHAT_ID_STR = os.getenv("GROUP_CHAT_ID")
GROUP_CHAT_ID = None

# Преобразуем GROUP_CHAT_ID в int, если он установлен
if GROUP_CHAT_ID_STR:
    try:
        GROUP_CHAT_ID = int(GROUP_CHAT_ID_STR)
        logger.info(f"GROUP_CHAT_ID successfully set to: {GROUP_CHAT_ID}")
    except ValueError:
        logger.error(f"Invalid GROUP_CHAT_ID format: {GROUP_CHAT_ID_STR}. Must be an integer.")
else:
    logger.warning("GROUP_CHAT_ID not set. Group notifications will be disabled.")

# Ensure essential variables are set
if not BOT_TOKEN:
    raise ValueError("No BOT_TOKEN found in environment variables")