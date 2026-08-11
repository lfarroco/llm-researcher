from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

if settings.database_url.startswith("sqlite") and ":memory:" in settings.database_url:
    # Plain in-memory SQLite creates a fresh empty database per connection.
    # Use a StaticPool so every connection (SessionLocal users included)
    # shares ONE in-memory database. `check_same_thread` allows the
    # background task worker to hand sessions off across threads.
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(settings.database_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    yield db
    db.close()
