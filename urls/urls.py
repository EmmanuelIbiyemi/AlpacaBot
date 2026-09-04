import os
from dotenv import load_dotenv

load_dotenv()

ENDPOINT = os.getenv("ENDPOINT")
APIKEY = os.getenv("API_KEY")
APISECRET = os.getenv("API_SECRET")
DEEPSEEK_API_KEY = os.getenv("DEEP_SEEK_API_KEY")

