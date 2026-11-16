from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings


def _normalize_url(url: str) -> str:
    # Railway/Render는 postgres:// 또는 postgresql:// 로 준다. psycopg(v3) 드라이버를 쓰도록 맞춘다.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


_url = _normalize_url(settings.DATABASE_URL)
_connect_args = {"check_same_thread": False} if _url.startswith("sqlite") else {}
engine = create_engine(_url, pool_pre_ping=True, connect_args=_connect_args)


def create_db_and_tables() -> None:
    from app import models  # noqa: F401  테이블 등록

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
