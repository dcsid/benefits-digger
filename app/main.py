from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base, SessionLocal, engine, get_db
from app.hybrid_explorer import hybrid_explorer_search
from app.models import ScreeningSession
from app.schemas import AnswerPayload, ComparePayload, ExplorerSearchPayload, SessionCreatePayload, SessionEnvelope
from app.services import (
    bootstrap_catalog,
    compare_scenarios,
    compute_results,
    compute_plan,
    create_session,
    get_next_question,
    get_program_detail,
    get_session_or_404,
    get_answers_map,
    list_program_catalog,
    list_review_tasks,
    list_states,
    provisional_result_count,
    serialize_question,
    sync_remote_sources,
    upsert_answers,
)


settings = get_settings()


def _migrate_depth_value(db_engine):
    """Add depth_value column to screening_sessions if missing (SQLite)."""
    from sqlalchemy import inspect as sa_inspect, text
    inspector = sa_inspect(db_engine)
    if "screening_sessions" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("screening_sessions")}
        if "depth_value" not in cols:
            with db_engine.begin() as conn:
                conn.execute(text("ALTER TABLE screening_sessions ADD COLUMN depth_value REAL DEFAULT 0.5"))


def _migrate_breadth_value(db_engine):
    """Add breadth_value column to screening_sessions if missing (SQLite)."""
    from sqlalchemy import inspect as sa_inspect, text
    inspector = sa_inspect(db_engine)
    if "screening_sessions" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("screening_sessions")}
        if "breadth_value" not in cols:
            with db_engine.begin() as conn:
                conn.execute(text("ALTER TABLE screening_sessions ADD COLUMN breadth_value REAL DEFAULT 0.5"))
                if "depth_value" in cols:
                    conn.execute(text("UPDATE screening_sessions SET breadth_value = COALESCE(depth_value, 0.5)"))


def _migrate_documents_json(db_engine):
    """Add documents_json column to programs if missing (SQLite)."""
    from sqlalchemy import inspect as sa_inspect, text
    inspector = sa_inspect(db_engine)
    if "programs" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("programs")}
        if "documents_json" not in cols:
            with db_engine.begin() as conn:
                conn.execute(text("ALTER TABLE programs ADD COLUMN documents_json JSON"))


def _migrate_amount_rule_formulas(db_engine):
    """Add formula columns to amount_rules if missing (SQLite)."""
    from sqlalchemy import inspect as sa_inspect, text
    inspector = sa_inspect(db_engine)
    if "amount_rules" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("amount_rules")}
        with db_engine.begin() as conn:
            if "formula_json" not in cols:
                conn.execute(text("ALTER TABLE amount_rules ADD COLUMN formula_json JSON"))
            if "input_keys" not in cols:
                conn.execute(text("ALTER TABLE amount_rules ADD COLUMN input_keys JSON"))
            if "min_amount" not in cols:
                conn.execute(text("ALTER TABLE amount_rules ADD COLUMN min_amount REAL"))
            if "max_amount" not in cols:
                conn.execute(text("ALTER TABLE amount_rules ADD COLUMN max_amount REAL"))
            if "period" not in cols:
                conn.execute(text("ALTER TABLE amount_rules ADD COLUMN period VARCHAR(32)"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    _migrate_depth_value(engine)
    _migrate_breadth_value(engine)
    _migrate_documents_json(engine)
    _migrate_amount_rule_formulas(engine)
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
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def require_admin_key(x_admin_key: str = Header(default="")) -> None:
    if not settings.admin_key:
        return
    if x_admin_key != settings.admin_key:
        raise HTTPException(status_code=401, detail="Invalid or missing admin key")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(settings.static_dir / "index.html")


@app.get("/dashboard", include_in_schema=False)
def dashboard_page() -> FileResponse:
    return FileResponse(settings.static_dir / "dashboard.html")


@app.get("/results", include_in_schema=False)
def results_page() -> FileResponse:
    return FileResponse(settings.static_dir / "results.html")


@app.get("/whatif", include_in_schema=False)
def whatif_page() -> FileResponse:
    return FileResponse(settings.static_dir / "whatif.html")


@app.get("/explorer", include_in_schema=False)
def explorer_page() -> FileResponse:
    return FileResponse(settings.static_dir / "explorer.html")


@app.get("/health")
def health_check(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.get(f"{settings.api_v1_prefix}/jurisdictions/states")
def states(db: Session = Depends(get_db)) -> list[dict[str, str]]:
    return list_states(db)


@app.get(f"{settings.api_v1_prefix}/programs")
def program_catalog(
    query: str = "",
    scope: str = "both",
    state_code: Optional[str] = None,
    categories: str = "",
    limit: int = 40,
    db: Session = Depends(get_db),
) -> list[dict]:
    category_list = [item.strip() for item in categories.split(",") if item.strip()]
    return list_program_catalog(
        db,
        query=query,
        scope=scope,
        state_code=state_code,
        categories=category_list,
        limit=min(max(limit, 1), 100),
    )


@app.post(f"{settings.api_v1_prefix}/explorer/search")
def explorer_search(payload: ExplorerSearchPayload, db: Session = Depends(get_db)) -> dict:
    return hybrid_explorer_search(
        db,
        query=payload.query,
        description=payload.description,
        scope=payload.scope,
        state_code=payload.state_code,
        categories=payload.categories,
        limit=payload.limit,
        use_llm=payload.use_llm,
    )


@app.post(f"{settings.api_v1_prefix}/sessions", response_model=SessionEnvelope)
def create_screening_session(payload: SessionCreatePayload, db: Session = Depends(get_db)) -> SessionEnvelope:
    session = create_session(
        db,
        scope=payload.scope,
        state_code=payload.state_code,
        categories=payload.categories,
        depth_mode=payload.depth_mode or "standard",
        breadth_value=payload.breadth_value,
        depth_value=payload.depth_value,
    )
    answers = get_answers_map(db, session)
    next_question = get_next_question(db, session, answers)
    return SessionEnvelope(
        session_id=session.public_id,
        next_question=serialize_question(db, next_question, session.depth_value),
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
        next_question=serialize_question(db, next_question, session.depth_value),
        provisional_result_count=provisional_result_count(db, session),
    )


@app.get(f"{settings.api_v1_prefix}/sessions/{{session_id}}/results")
def screening_results(session_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        session = get_session_or_404(db, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return compute_results(db, session)


@app.get(f"{settings.api_v1_prefix}/sessions/{{session_id}}/plan")
def screening_plan(session_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        session = get_session_or_404(db, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return compute_plan(db, session)


@app.post(f"{settings.api_v1_prefix}/sessions/{{session_id}}/compare")
def screening_compare(session_id: str, payload: ComparePayload, db: Session = Depends(get_db)) -> dict:
    try:
        session = get_session_or_404(db, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return compare_scenarios(
        db,
        session,
        [
            {
                "name": scenario.name,
                "description": scenario.description,
                "answers": scenario.answers,
            }
            for scenario in payload.scenarios
        ],
    )


@app.get(f"{settings.api_v1_prefix}/programs/{{slug}}")
def program_detail(slug: str, db: Session = Depends(get_db)) -> dict:
    payload = get_program_detail(db, slug)
    if payload is None:
        raise HTTPException(status_code=404, detail="Program not found")
    return payload


@app.get(f"{settings.api_v1_prefix}/admin/review-tasks")
def review_tasks(db: Session = Depends(get_db), _auth: None = Depends(require_admin_key)) -> list[dict]:
    return list_review_tasks(db)


@app.post(f"{settings.api_v1_prefix}/admin/sync")
def admin_sync(db: Session = Depends(get_db), _auth: None = Depends(require_admin_key)) -> dict:
    summary = sync_remote_sources(db)
    summary["review_tasks"] = list_review_tasks(db)
    return summary


app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
