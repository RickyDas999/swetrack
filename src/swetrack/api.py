"""FastAPI service: opportunity ranking/readiness endpoints plus the application pipeline.

The sentence-embedding model is never touched by /health or /jobs. It is
only loaded, lazily and cached once per process, the first time a
POST /recommend or GET /opportunities/{id}/readiness request selects
ranker="embedding" (see swetrack.domains.opportunities.ranking.embeddings).

The /applications endpoints (CLAUDE.md Phase 12) track a candidate's
recruiting pipeline per job -- no ML involved, plain CRUD-style persistence
over the applications domain.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

from swetrack import __version__
from swetrack.domains.applications.schemas import (
    Application,
    ApplicationStatusEvent,
    CreateApplicationRequest,
    TransitionStatusRequest,
)
from swetrack.domains.applications.schemas import ApplicationStatus as ApplicationStatusType
from swetrack.domains.applications.services import (
    create_application,
    get_application,
    get_application_history,
    list_applications,
    transition_status,
)
from swetrack.domains.interviews.schemas import CreateInterviewRequest, Interview
from swetrack.domains.interviews.schemas import RoundType as RoundTypeType
from swetrack.domains.interviews.services import create_interview, get_interview, list_interviews
from swetrack.domains.opportunities.config import DataLoadError, load_candidate_profile, load_jobs
from swetrack.domains.opportunities.models import (
    HealthResponse,
    JobRecord,
    RankerName,
    RecommendRequest,
    RecommendResponse,
)
from swetrack.domains.opportunities.ranking.base import Ranker
from swetrack.domains.opportunities.ranking.embeddings import EmbeddingRanker
from swetrack.domains.opportunities.ranking.tfidf import TfidfRanker
from swetrack.domains.opportunities.readiness import ReadinessResult, compute_readiness
from swetrack.infrastructure.database.base import get_engine, get_sessionmaker, init_db

app = FastAPI(title="SWETrack API", version=__version__)

# Module-level so every request reuses one connection pool rather than
# opening a fresh engine per call; defaults to the local SQLite file under
# var/ (see infrastructure/database/base.py), overridable via
# SWETRACK_DATABASE_URL for e.g. Postgres later.
_engine = get_engine()
init_db(_engine)
_SessionLocal = get_sessionmaker(_engine)


def get_db_session() -> Iterator[Session]:
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _build_ranker(name: str) -> Ranker:
    """Construct a ranker by name. `name` is already Literal-validated by RecommendRequest."""
    if name == "embedding":
        return EmbeddingRanker()
    return TfidfRanker()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Service health check. Does not load the sentence-transformer model."""
    return HealthResponse(version=__version__)


@app.get("/jobs", response_model=list[JobRecord])
def get_jobs(
    limit: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
) -> list[JobRecord]:
    """Return available job metadata, optionally paginated with limit/offset."""
    try:
        jobs = load_jobs()
    except DataLoadError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if limit is None:
        return jobs[offset:]
    return jobs[offset : offset + limit]


@app.post("/recommend", response_model=RecommendResponse)
def recommend(request: RecommendRequest) -> RecommendResponse:
    """Rank jobs against a supplied (or explicitly requested example) candidate profile."""
    try:
        jobs = load_jobs()
    except DataLoadError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if request.top_k > len(jobs):
        raise HTTPException(
            status_code=422,
            detail=f"top_k={request.top_k} exceeds available jobs ({len(jobs)}).",
        )

    profile = request.profile
    if profile is None:
        try:
            profile = load_candidate_profile()
        except DataLoadError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    ranker = _build_ranker(request.ranker)
    results = ranker.recommend(profile, jobs, request.top_k)
    return RecommendResponse(ranker=request.ranker, top_k=request.top_k, results=results)


@app.get("/opportunities/{job_id}/readiness", response_model=ReadinessResult)
def get_readiness(
    job_id: str,
    ranker: RankerName = Query(default="tfidf"),
    session: Session = Depends(get_db_session),
) -> ReadinessResult:
    """Role Fit and Readiness for one job, against the example candidate profile and tracked mastery.

    There is no per-request candidate profile here (unlike POST /recommend):
    a GET request has no body, and this is a single-user local app with no
    auth/user concept (CLAUDE.md explicitly avoids that), so the example
    profile is the only candidate representation available.
    """
    try:
        jobs = load_jobs()
    except DataLoadError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    job = next((candidate for candidate in jobs if candidate.job_id == job_id), None)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id!r}")

    try:
        profile = load_candidate_profile()
    except DataLoadError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return compute_readiness(session, job=job, profile=profile, ranker=_build_ranker(ranker))


@app.post("/applications", response_model=Application, status_code=201)
def post_application(
    request: CreateApplicationRequest, session: Session = Depends(get_db_session)
) -> Application:
    """Start tracking an application to a job, at an optional initial status (default 'discovered')."""
    try:
        application, _ = create_application(
            session, job_id=request.job_id, status=request.status, notes=request.notes
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return application


@app.get("/applications", response_model=list[Application])
def get_applications(
    status: ApplicationStatusType | None = Query(default=None),
    job_id: str | None = Query(default=None),
    session: Session = Depends(get_db_session),
) -> list[Application]:
    """List tracked applications, optionally filtered by current status and/or job."""
    return list_applications(session, status=status, job_id=job_id)


@app.get("/applications/{application_id}", response_model=Application)
def get_application_by_id(application_id: str, session: Session = Depends(get_db_session)) -> Application:
    application = get_application(session, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail=f"Unknown application_id: {application_id!r}")
    return application


@app.post("/applications/{application_id}/status", response_model=Application)
def post_application_status(
    application_id: str, request: TransitionStatusRequest, session: Session = Depends(get_db_session)
) -> Application:
    """Move an application to a new status, recording one immutable history event."""
    try:
        application, _ = transition_status(
            session, application_id=application_id, to_status=request.status, notes=request.notes
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return application


@app.get("/applications/{application_id}/history", response_model=list[ApplicationStatusEvent])
def get_application_status_history(
    application_id: str, session: Session = Depends(get_db_session)
) -> list[ApplicationStatusEvent]:
    """An application's full immutable status transition history, in chronological order."""
    if get_application(session, application_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown application_id: {application_id!r}")
    return get_application_history(session, application_id)


@app.post("/interviews", response_model=Interview, status_code=201)
def post_interview(request: CreateInterviewRequest, session: Session = Depends(get_db_session)) -> Interview:
    """Log one interview round. Emits SkillEvents/mastery updates only if `result` is decided."""
    try:
        interview, _ = create_interview(
            session,
            company=request.company,
            role=request.role,
            round_type=request.round_type,
            date=request.date,
            skills_tested=request.skills_tested,
            result=request.result,
            notes=request.notes,
            feedback=request.feedback,
            application_id=request.application_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return interview


@app.get("/interviews", response_model=list[Interview])
def get_interviews(
    application_id: str | None = Query(default=None),
    round_type: RoundTypeType | None = Query(default=None),
    session: Session = Depends(get_db_session),
) -> list[Interview]:
    """List logged interviews, optionally filtered by application and/or round type."""
    return list_interviews(session, application_id=application_id, round_type=round_type)


@app.get("/interviews/{interview_id}", response_model=Interview)
def get_interview_by_id(interview_id: str, session: Session = Depends(get_db_session)) -> Interview:
    interview = get_interview(session, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail=f"Unknown interview_id: {interview_id!r}")
    return interview
