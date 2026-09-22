"""FastAPI service: opportunity ranking/readiness endpoints plus the application pipeline.

The sentence-embedding model is never touched by /health or /jobs. It is
only loaded, lazily and cached once per process, the first time a
POST /recommend or GET /opportunities/{id}/readiness request selects
ranker="embedding" (see swetrack.domains.opportunities.ranking.embeddings).

The /applications endpoints (CLAUDE.md Phase 12) track a candidate's
recruiting pipeline per job -- no ML involved, plain CRUD-style persistence
over the applications domain.

GET / serves a static, read-only dashboard UI (src/swetrack/static/dashboard.html)
that fetches from the same API below -- same-origin, so no CORS middleware
is needed.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from swetrack import __version__
from swetrack.domains.applications.priority import (
    ApplicationPriority,
    compute_application_priority,
    rank_application_priorities,
)
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
from swetrack.domains.jobs.eligibility import EligibilityStatus as EligibilityStatusType
from swetrack.domains.jobs.inbox import InboxEntry, list_inbox
from swetrack.domains.jobs.services import list_discovered_job_records
from swetrack.domains.learning.schemas import InterviewReadinessSummary, SkillMasterySummary, StudyRecommendation
from swetrack.domains.learning.services import (
    get_interview_readiness_summary,
    get_study_recommendations,
    list_mastery,
)
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
from swetrack.domains.skills.models import SkillCategory as SkillCategoryType
from swetrack.infrastructure.database.base import get_engine, get_sessionmaker, init_db
from swetrack.infrastructure.paths import find_repo_root

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


def _load_all_jobs(session: Session) -> list[JobRecord]:
    """Sample/CSV jobs plus every persisted, non-duplicate Job Radar discovered job.

    Centralizes the try/except around `load_jobs()` that every job-reading
    endpoint below previously repeated, and is the one place discovered
    jobs (Job Radar Checkpoint 3) join the existing ranking/readiness/
    priority pipeline -- see docs/job-radar-integration-plan.md Section 7.
    """
    try:
        sample_jobs = load_jobs()
    except DataLoadError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return sample_jobs + list_discovered_job_records(session)


_STATIC_DIR = find_repo_root() / "src" / "swetrack" / "static"


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    """Serve the read-only dashboard UI. Same-origin fetches to the API below -- no CORS needed."""
    return FileResponse(_STATIC_DIR / "dashboard.html")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Service health check. Does not load the sentence-transformer model."""
    return HealthResponse(version=__version__)


@app.get("/jobs", response_model=list[JobRecord])
def get_jobs(
    limit: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db_session),
) -> list[JobRecord]:
    """Return available job metadata (sample + Job Radar discovered), optionally paginated."""
    jobs = _load_all_jobs(session)
    if limit is None:
        return jobs[offset:]
    return jobs[offset : offset + limit]


@app.get("/jobs/inbox", response_model=list[InboxEntry])
def get_jobs_inbox(
    eligibility_status: EligibilityStatusType | None = Query(default=None),
    application_status: ApplicationStatusType | None = Query(default=None),
    min_priority: float | None = Query(default=None, ge=0.0, le=1.0),
    since_hours: float | None = Query(default=None, gt=0.0),
    ranker: RankerName = Query(default="tfidf"),
    session: Session = Depends(get_db_session),
) -> list[InboxEntry]:
    """Job Radar inbox: discovered jobs enriched with eligibility, discovery timing, and priority.

    Registered before GET /jobs/{job_id}-shaped routes would be (none exist
    yet) so "inbox" is never mistaken for a job_id. Every entry keeps
    `source_published_at` ("published") separate from `first_seen_at`
    ("first found") -- never conflated, per CLAUDE.md Section 8.
    """
    try:
        profile = load_candidate_profile()
    except DataLoadError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return list_inbox(
        session,
        ranker=_build_ranker(ranker),
        profile=profile,
        eligibility_status=eligibility_status,
        application_status=application_status,
        min_priority=min_priority,
        since_hours=since_hours,
    )


@app.post("/recommend", response_model=RecommendResponse)
def recommend(request: RecommendRequest, session: Session = Depends(get_db_session)) -> RecommendResponse:
    """Rank jobs against a supplied (or explicitly requested example) candidate profile."""
    jobs = _load_all_jobs(session)

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
    jobs = _load_all_jobs(session)

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


@app.get("/applications/priority", response_model=list[ApplicationPriority])
def get_applications_priority(
    status: ApplicationStatusType | None = Query(default=None),
    top_k: int = Query(default=10, ge=1),
    ranker: RankerName = Query(default="tfidf"),
    session: Session = Depends(get_db_session),
) -> list[ApplicationPriority]:
    """Rank tracked applications by priority, highest first -- the "Top Opportunities" list.

    Registered before GET /applications/{application_id} so "priority" is
    never matched as an application_id path parameter.
    """
    applications = list_applications(session, status=status)
    jobs_by_id = {job.job_id: job for job in _load_all_jobs(session)}

    try:
        profile = load_candidate_profile()
    except DataLoadError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    ranked = rank_application_priorities(
        session, applications=applications, jobs_by_id=jobs_by_id, profile=profile, ranker=_build_ranker(ranker)
    )
    return ranked[:top_k]


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


@app.get("/applications/{application_id}/priority", response_model=ApplicationPriority)
def get_application_priority(
    application_id: str,
    ranker: RankerName = Query(default="tfidf"),
    session: Session = Depends(get_db_session),
) -> ApplicationPriority:
    """Role Fit, Readiness, and preference match for one tracked application, combined into one score.

    Uses the example candidate profile, same as GET /opportunities/{id}/readiness
    (no per-request profile: a GET request has no body, and this is a
    single-user local app with no auth/user concept).
    """
    application = get_application(session, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail=f"Unknown application_id: {application_id!r}")

    jobs = _load_all_jobs(session)

    job = next((candidate for candidate in jobs if candidate.job_id == application.job_id), None)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {application.job_id!r}")

    try:
        profile = load_candidate_profile()
    except DataLoadError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return compute_application_priority(
        session, application=application, job=job, profile=profile, ranker=_build_ranker(ranker)
    )


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


@app.get("/mastery", response_model=list[SkillMasterySummary])
def get_mastery_list(
    top_k: int | None = Query(default=None, ge=1),
    category: SkillCategoryType | None = Query(default=None),
    session: Session = Depends(get_db_session),
) -> list[SkillMasterySummary]:
    """Mastery for every canonical skill, weakest first. Optional `category` filter and `top_k` cap.

    Every taxonomy skill is included, not just practiced ones -- see
    `learning.services.list_mastery` for why (an unpracticed skill can still
    be the weakest).
    """
    summaries = list_mastery(session)
    if category is not None:
        summaries = [summary for summary in summaries if summary.category == category]
    return summaries[:top_k] if top_k is not None else summaries


@app.get("/mastery/summary", response_model=InterviewReadinessSummary)
def get_mastery_summary(session: Session = Depends(get_db_session)) -> InterviewReadinessSummary:
    """Mastery averaged per skill category, plus a coarse coding/system-design rollup."""
    return get_interview_readiness_summary(session)


@app.get("/recommendations", response_model=list[StudyRecommendation])
def get_recommendations(
    top_k: int = Query(default=5, ge=1),
    session: Session = Depends(get_db_session),
) -> list[StudyRecommendation]:
    """Adaptive study recommendations across every tracked skill, unfiltered by any one job.

    The same heuristic ranker `GET /opportunities/{id}/readiness` uses
    (filtered to one job's required skills there); here it ranks over every
    skill any tracked activity touches.
    """
    return get_study_recommendations(session, top_k=top_k)
