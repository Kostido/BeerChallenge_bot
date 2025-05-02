import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Bot token from environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Ensure essential variables are set
if not BOT_TOKEN:
    raise ValueError("No BOT_TOKEN found in environment variables")