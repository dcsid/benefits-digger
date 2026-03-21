from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base, SessionLocal, engine, get_db
from app.models import ScreeningSession
from app.schemas import AnswerPayload, SessionCreatePayload, SessionEnvelope
from app.services import (
    bootstrap_catalog,
    compute_results,
    create_session,
    get_next_question,
    get_program_detail,
    get_session_or_404,
    get_answers_map,
    list_review_tasks,
    list_states,
    provisional_result_count,
    serialize_question,
    sync_remote_sources,
    upsert_answers,
)


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        bootstrap_catalog(db, use_remote=settings.auto_sync_remote)
        yield
    finally:
        db.close()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(settings.static_dir / "index.html")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get(f"{settings.api_v1_prefix}/jurisdictions/states")
def states(db: Session = Depends(get_db)) -> list[dict[str, str]]:
    return list_states(db)


@app.post(f"{settings.api_v1_prefix}/sessions", response_model=SessionEnvelope)
def create_screening_session(payload: SessionCreatePayload, db: Session = Depends(get_db)) -> SessionEnvelope:
    session = create_session(
        db,
        scope=payload.scope,
        state_code=payload.state_code,
        categories=payload.categories,
        depth_mode=payload.depth_mode,
    )
    answers = get_answers_map(db, session)
    next_question = get_next_question(db, session, answers)
    return SessionEnvelope(
        session_id=session.public_id,
        next_question=serialize_question(db, next_question),
        provisional_result_count=provisional_result_count(db, session),
    )


@app.post(f"{settings.api_v1_prefix}/sessions/{{session_id}}/answers", response_model=SessionEnvelope)
def answer_screening_question(
    session_id: str,
    payload: AnswerPayload,
    db: Session = Depends(get_db),
) -> SessionEnvelope:
    try:
        session = get_session_or_404(db, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    upsert_answers(db, session, payload.answers)
    answers = get_answers_map(db, session)
    next_question = get_next_question(db, session, answers)
    return SessionEnvelope(
        session_id=session.public_id,
        next_question=serialize_question(db, next_question),
        provisional_result_count=provisional_result_count(db, session),
    )


@app.get(f"{settings.api_v1_prefix}/sessions/{{session_id}}/results")
def screening_results(session_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        session = get_session_or_404(db, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return compute_results(db, session)


@app.get(f"{settings.api_v1_prefix}/programs/{{slug}}")
def program_detail(slug: str, db: Session = Depends(get_db)) -> dict:
    payload = get_program_detail(db, slug)
    if payload is None:
        raise HTTPException(status_code=404, detail="Program not found")
    return payload


@app.get(f"{settings.api_v1_prefix}/admin/review-tasks")
def review_tasks(db: Session = Depends(get_db)) -> list[dict]:
    return list_review_tasks(db)


@app.post(f"{settings.api_v1_prefix}/admin/sync")
def admin_sync(db: Session = Depends(get_db)) -> dict:
    summary = sync_remote_sources(db)
    summary["review_tasks"] = list_review_tasks(db)
    return summary
