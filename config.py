import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Bot token from environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Group chat ID for sharing beer submissions
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")

# Ensure essential variables are set
if not BOT_TOKEN:
    raise ValueError("No BOT_TOKEN found in environment variables")