import os

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
DEFAULT_CAMPAIGN_LANGUAGE = os.getenv("DEFAULT_CAMPAIGN_LANGUAGE", "pl")
APP_ENV = os.getenv("APP_ENV", "dev")
