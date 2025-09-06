from dotenv import load_dotenv
import os

load_dotenv()
TG_TOKEN = os.getenv("TG_TOKEN")
AI_TOKEN = os.getenv("AI_TOKEN")
SHOP_ID = os.getenv("SHOP_ID")
YK_TOKEN = os.getenv("YK_TOKEN")

id={}
MAX_MSG_LEN = 4000  # оставляем немного запас для безопасной отправки
