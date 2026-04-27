import os


DEFAULT_DB_PATH = "/data/ai_gm.db"
DEFAULT_TEST_DB_PATH = "/data/test_ai.db"


def resolve_db_path() -> str:
    if os.getenv("AI_TEST_MODE") == "1":
        return os.getenv("AI_TEST_DB_PATH", DEFAULT_TEST_DB_PATH)
    return DEFAULT_DB_PATH


def resolve_database_url() -> str:
    if os.getenv("AI_TEST_MODE") == "1":
        path = resolve_db_path()
        if path.startswith("sqlite:"):
            return path
        return f"sqlite:///{path}"
    return os.getenv("DATABASE_URL", "sqlite:////data/ai_gm.db")
