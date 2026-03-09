from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:5433/vyapaar_bandhu"
)

# Use SSL only for Render (not for local)
if "render.com" in DATABASE_URL or "dpg-" in DATABASE_URL:
    engine = create_engine(DATABASE_URL, connect_args={"sslmode": "require"})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()