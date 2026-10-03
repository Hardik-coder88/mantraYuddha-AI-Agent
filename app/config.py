import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))

MODEL = os.getenv("MODEL", "claude-sonnet-5-5")
DATA_DIR = os.getenv("DATA_DIR", os.path.join(BASE_DIR, "data", "public"))
if not os.path.isabs(DATA_DIR):
    DATA_DIR = os.path.join(BASE_DIR, DATA_DIR)
TZ_NAME = os.getenv("TZ_NAME", "Asia/Kolkata")
MAX_TURNS = 8
PROMPT_PATH = os.path.join(BASE_DIR, "prompts", "system_prompt.md")

# Real NovaMart public dataset mapping.
FILES = {
    "customers": "customers.csv",
    "products": "products.csv",
    "orders": "orders.csv",
    "order_items": "order_items.csv",
    "support_tickets": "support_tickets.csv",
    "reviews": "reviews.csv",
    "conversations": "conversations.json",
}
POLICY_DIR = os.path.join(DATA_DIR, "policies")
PRODUCT_DOC_DIR = os.path.join(DATA_DIR, "products")
