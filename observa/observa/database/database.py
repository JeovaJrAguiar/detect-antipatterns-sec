# observa/database.py
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os

# Carrega variáveis do arquivo .env (se existir)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    required_settings = ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_DB")
    missing_settings = [name for name in required_settings if not os.getenv(name)]
    if missing_settings:
        raise RuntimeError(
            "Database configuration is incomplete. Set DATABASE_URL or provide: "
            + ", ".join(required_settings)
        )

    DATABASE_URL = URL.create(
        drivername="postgresql+psycopg2",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ["POSTGRES_HOST"],
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.environ["POSTGRES_DB"],
    )

# Cria o engine SQLAlchemy
engine = create_engine(DATABASE_URL, echo=False, future=True)

# Cria o factory para sessões
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

# Base para os modelos ORM
Base = declarative_base()
