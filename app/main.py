from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import create_db_and_tables
from app.errors import register_error_handlers
from app.openapi_docs import install_openapi
from app.routers import admin, auth, courses, history, live, questions, stream


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(title="모름지기 API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

for r in (auth, courses, history, live, questions, stream, admin):
    app.include_router(r.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok", "env": settings.ENV, "demo_always_live": settings.DEMO_ALWAYS_LIVE}


install_openapi(app)  # Swagger에 실제 오류 코드 표시 (app/openapi_docs.py)
