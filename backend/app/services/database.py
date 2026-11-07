import psycopg
from app.core.config import settings


def get_connection():
    """Create a short-lived psycopg connection from the configured SQLAlchemy URL."""
    dsn = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    return psycopg.connect(dsn)
