# Job Radar Integration Plan (Checkpoint 0)

Audit date: 2026-09-21. Verified against the actual repository at commit `a11eee5`
and a live `pytest` run (**194 passed**, 42.6s, no failures/skips). This document,
not `SWETrack_Project_Context_Update.md` or `SWETrack_Job_Radar_Claude_Code_Handoff.md`,
is the record of what actually exists today; discrepancies from those two documents
are called out explicitly in Section 13.

No production code was changed to produce this document.

> **Status as of Checkpoint 5 (later update):** everything this document
> planned for Checkpoints 1–5 has since been built — ingestion adapters,
> `discovered_jobs` persistence/dedup, eligibility/freshness/priority, the
> job inbox and notifications, and resume evidence/tailoring. This document
> is preserved as the original planning and decision record (including the
> resolved open questions in Section 9 — `discovered_jobs` naming, the
> auto-create-application design, and the separate candidate eligibility
> config), not as a description of current unstarted work. See `README.md`
> and `git log` for current state.

---

## 1. Current repository architecture and verified implementation state

SWETrack is a Python 3.11 modular monolith, `src/` layout, package name `swetrack`
(already fully renamed from `rolerank` — Phases M1/M2 of `CLAUDE.md` are done).

```
src/swetrack/
├── api.py                              # single FastAPI app, every route
├── domains/
│   ├── opportunities/                  # ranking, readiness, config/data loading
│   │   ├── config.py                   # CSV/YAML loaders (jobs, profile, labels)
│   │   ├── models.py                   # CandidateProfile, JobRecord, API I/O schemas
│   │   ├── preprocessing.py, evaluation.py
│   │   ├── readiness.py                # Role Fit + Readiness
│   │   └── ranking/{base,tfidf,embeddings}.py
│   ├── applications/                   # recruiting pipeline + Application Priority
│   │   ├── models.py (SQLAlchemy) / schemas.py (Pydantic) / services.py
│   │   └── priority.py
│   ├── interviews/                     # interview rounds -> mastery
│   ├── skills/                         # taxonomy.py (37 skills/8 categories) + normalization.py
│   └── learning/                       # activities, immutable attempts/SkillEvents, mastery cache
├── ml/
│   ├── knowledge_tracing/bkt.py
│   ├── study_ranking/ranker.py
│   ├── application_priority/ranker.py
│   └── evaluation/knowledge_tracing.py
├── infrastructure/
│   ├── database/base.py                # SQLAlchemy engine/session, SQLite, create_all (no Alembic)
│   └── paths.py                        # find_repo_root()
└── static/dashboard.html               # plain HTML/JS dashboard, served at GET /
```

No `api/` subpackage, no `ingestion/`, no `cli/` package (CLI is two top-level
`scripts/*.py` files), no `resume/` directory, no React/frontend build, no Alembic,
no `httpx` runtime dependency. These are gaps relative to the handoff's suggested
layout, not bugs — they simply haven't been built yet.

### Verified implementation matrix

| Handoff area | Status | Evidence |
|---|---|---|
| FastAPI backend | **VERIFIED** | `src/swetrack/api.py`, 194 passing tests incl. `tests/test_api*.py` |
| SQLAlchemy + local SQLite | **VERIFIED** | `infrastructure/database/base.py`; `var/swetrack.db` present |
| TF-IDF ranker | **VERIFIED** | `ranking/tfidf.py`, `tests/test_rankers.py` |
| Sentence-Transformer (`all-MiniLM-L6-v2`) ranker | **VERIFIED** | `ranking/embeddings.py`, lazy-loaded per README/api.py docstring |
| Precision@K / NDCG@K evaluation | **VERIFIED** | `opportunities/evaluation.py`, `tests/test_evaluation.py`, `scripts/run_experiment.py` |
| Local MLflow tracking | **VERIFIED** | `mlruns/` contains real logged runs; `scripts/run_experiment.py` |
| Canonical skill taxonomy + alias normalization | **VERIFIED** | `skills/taxonomy.py`, `skills/normalization.py`, `tests/test_skills.py` |
| Immutable `SkillEvent` history | **VERIFIED** | `learning/models.py::SkillEventRecord`, insert-only in `services.py` |
| Coding practice tracking | **VERIFIED** | `learning/models.py::CodingAttemptRecord`, `tests/test_coding_practice.py` |
| System Design practice (multi-skill rubric) | **VERIFIED** | `tests/test_system_design_practice.py` |
| Bayesian Knowledge Tracing | **VERIFIED** | `ml/knowledge_tracing/bkt.py`, `tests/test_bkt.py`, `scripts/run_knowledge_tracing_experiment.py` |
| Explainable study ranking | **VERIFIED** | `ml/study_ranking/ranker.py`, `tests/test_study_ranking.py` |
| **Role Fit** (`/opportunities/{id}/readiness`) | **VERIFIED** | `opportunities/readiness.py`, `tests/test_readiness.py` |
| **Readiness** (separate score) | **VERIFIED** | same file — kept as a distinct field, never blended |
| Application pipeline (statuses, immutable history) | **VERIFIED** | `applications/models.py`, `tests/test_applications.py`, `tests/test_api_applications.py` |
| Interview tracking -> SkillEvents | **VERIFIED** | `interviews/services.py`, `tests/test_interviews.py`, `tests/test_api_interviews.py` |
| **Application Priority** (6-component, separate from Fit/Readiness) | **VERIFIED** | `applications/priority.py`, `ml/application_priority/ranker.py`, `tests/test_application_priority.py` |
| Mastery/category rollup endpoints (`/mastery`, `/mastery/summary`, `/recommendations`) | **VERIFIED** | `tests/test_api_mastery.py`, `tests/test_mastery_overview.py` |
| Dashboard UI | **VERIFIED (manual, per README)** | `static/dashboard.html`; not covered by `pytest` |
| Docker | **VERIFIED (manual, per README)** | `Dockerfile`; README documents an end-to-end manual run; not covered by CI |
| CI (GitHub Actions) | **VERIFIED** | `.github/workflows/ci.yml`, added in the most recent commit |
| React frontend | **NOT IMPLEMENTED** | grep confirms no `frontend/` directory, no `package.json` |
| Job ingestion (Greenhouse/Lever/Ashby) | **NOT IMPLEMENTED** | grep for `greenhouse\|lever\|ashby\|ingestion` returns nothing |
| `jobs` / `job_sources` / `job_assessments` DB tables | **NOT IMPLEMENTED** | jobs are file-backed (CSV), not ORM models |
| Resume tailoring / LaTeX / evidence library | **NOT IMPLEMENTED** | grep for `latex\|resume_evidence\|tailored_resume` returns nothing |
| macOS notifications / LaunchAgent | **NOT IMPLEMENTED** | no such code anywhere |
| Eligibility classifier / freshness scoring | **NOT IMPLEMENTED** | no such module |
| Alembic migrations | **NOT IMPLEMENTED** | `alembic` only present as a transitive dev-env package, not a project dependency; `init_db` uses `Base.metadata.create_all` |
| Lint/type checks (ruff/mypy) | **NOT CONFIGURED** | no config in `pyproject.toml` or CI — nothing to run for this checkpoint |

Everything the handoff calls PLANNED for Job Radar itself is, unsurprisingly,
**PLANNED**, not started. The surprise is on the other side: the *existing*
SWETrack repository already implements essentially all of `CLAUDE.md` Phases
0–14, including Role Fit, Readiness, and Application Priority as three
genuinely separate, explainable scores. Job Radar Checkpoint 3 ("rank new-grad
jobs with explainable eligibility... Role Fit, Readiness, and Priority stay
separate") is substantially less new work than the handoff assumes — it is
mostly *feeding new inputs* (discovered jobs, freshness, eligibility) into an
existing pipeline, not building that pipeline from scratch.

---

## 2. Existing components Job Radar can reuse as-is

- **`Ranker` interface** (`opportunities/ranking/base.py`) — `score_jobs(profile, jobs)`
  takes a plain `list[JobRecord]`. Discovered jobs only need to be turned into
  `JobRecord` instances; TF-IDF/embedding scoring needs zero changes.
- **`compute_readiness`** (`opportunities/readiness.py`) — already the exact
  `fit_score` / `readiness_score` / `skill_gaps` / `recommended_activities` shape
  the handoff's `GET /opportunities/{id}/readiness` response describes. Reusable
  unchanged for any `JobRecord`, discovered or sample.
- **`compute_application_priority` / `rank_application_priorities`**
  (`applications/priority.py`) — already combines Role Fit + Readiness +
  preference/company/compensation/deadline into one explainable score with
  visible components. This is most of Job Radar's Checkpoint 3 "Application
  Priority" requirement; it is missing only freshness and new-grad confidence
  as components (see Section 8).
- **`skills.normalization.normalize_skill`** — deterministic alias mapping,
  exactly what the handoff's JD skill-normalization step (Section 11) needs.
- **`ApplicationRecord` / `ApplicationStatusEventRecord` + `services.py`** — the
  application-lifecycle statuses the handoff wants (`discovered`, `applied`,
  `oa`, `rejected`, etc.) already exist as a `Literal` and an immutable event
  log. Job Radar's Checkpoint 5 "application tracking" is *already built* at
  the model level; it only needs a job source that isn't the sample CSV.
- **`infrastructure/database/base.py`** (`Base`, `get_engine`, `get_sessionmaker`,
  `init_db`) — new Job Radar ORM models register on the same `Base` and get
  picked up by `init_db`'s `create_all` with no plumbing changes.
- **`tests/conftest.py`'s `db_session` fixture** — in-memory SQLite pattern;
  new domain model modules just need a `# noqa: F401` import line added here
  (as `applications`/`interviews`/`learning` already do) so their tables exist
  in the test DB.
- **CI workflow** — `pip install -e ".[dev]"` + `pytest -q`; new dependencies
  Job Radar adds just need to land in `pyproject.toml`'s `dependencies`.

## 3. Existing interfaces that should remain unchanged

- `Ranker.score_jobs` / `Ranker.recommend` signatures — do not add job-source
  parameters here. If ingestion needs different jobs, pass a different `list[JobRecord]`.
- `CandidateProfile` — this is the *ranking-text* input (skills/experience/
  preferences), consumed by both rankers today. **Decided:** eligibility
  fields (`graduation_date`, `work_authorization`, `excluded_levels`,
  `target_roles` — handoff Section 3) do not get added here. They live in a
  new `config/candidate.example.yaml`, loaded by a new small Pydantic model
  read only by the eligibility classifier (Section 4). Reasoning: nothing in
  `CandidateProfile` today is consumed for pass/fail gating, only for
  similarity text and preference-overlap matching — eligibility fields have a
  different consumer (a deterministic hard gate, never a ranker) and adding
  them to `CandidateProfile` would force every existing call site and every
  test's inline `CandidateProfile(...)` construction to carry fields they
  never use. A separate file is zero-risk to the ~6 existing call sites and
  dozen-plus test fixtures already built around `CandidateProfile`'s current
  shape.
- `ReadinessResult` / `ApplicationPriority` response shapes — additive changes
  only (new optional fields), never restructuring `fit_score` vs.
  `readiness_score` vs. `score` into one number. This is the repository's most
  consistently enforced architectural rule and the thing `CLAUDE.md` most
  explicitly protects.
- `ApplicationStatus` literal and `transition_status`'s unconstrained
  transition graph — Job Radar does not need a stricter state machine; reuse
  as-is.
- `GET /applications/priority` route-ordering trick (registered before
  `GET /applications/{id}`) — any new collection-style route under
  `/applications/...` must follow the same "register the literal path before
  the parameterized one" pattern.

## 4. Exact files/modules to add

All new code lives under a new `domains/jobs/` package (naming: this repo
calls its domains by noun, e.g. `opportunities`, `applications` — "jobs" fits
that convention better than the handoff's proposed top-level `ingestion/`),
matching the existing `models.py` / `schemas.py` / `services.py` split every
other domain uses.

```
src/swetrack/domains/jobs/
├── __init__.py
├── models.py            # SQLAlchemy: JobSourceRecord, JobRecord (DB), JobAssessmentRecord
├── schemas.py            # Pydantic: NormalizedJob, JobSource read/write schemas
├── services.py           # upsert/dedup/query — the only write path to jobs.* tables
├── adapters/
│   ├── __init__.py
│   ├── base.py            # SourceAdapter protocol, returns list[NormalizedJob]
│   ├── greenhouse.py
│   ├── lever.py
│   ├── ashby.py
│   └── manual.py          # manual URL / pasted-JD import
├── normalize.py           # canonicalization: title/company/URL normalization, dedup keys
├── eligibility.py         # deterministic new-grad classifier (Checkpoint 3, not 1)
└── freshness.py           # freshness scoring (Checkpoint 3, not 1)

config/
├── candidate.example.yaml   # NEW: graduation/work-auth/target-role config (handoff Section 3)
└── sources.example.yaml     # NEW: ATS source registry (handoff Section 6)

tests/
├── fixtures/ats/
│   ├── greenhouse_sample.json
│   ├── lever_sample.json
│   └── ashby_sample.json
├── test_job_adapters.py
├── test_job_normalization.py
└── test_jobs_persistence.py     # Checkpoint 2

cli/
└── (extend scripts/, do not add a cli/ package yet — see Section 12)
```

Nothing here is implemented in this checkpoint; this is the target layout for
Checkpoints 1–3.

## 5. Exact existing files/modules that will need modification (future checkpoints)

| File | Change needed | Checkpoint |
|---|---|---|
| `pyproject.toml` | add `httpx` to core `dependencies` (currently dev-only, used only by `TestClient`); ingestion needs it at runtime | 1 |
| `tests/conftest.py` | import `domains.jobs.models` so its tables register in the in-memory test DB | 2 |
| `domains/opportunities/config.py` | `load_jobs()` currently reads only the CSV; needs a variant/parameter to also (or instead) read discovered jobs from the DB | 2–3 |
| `domains/applications/services.py` | `_job_exists()` currently checks only `load_jobs()` (CSV); must also recognize DB-backed discovered jobs once they exist | 2–3 |
| `domains/jobs/services.py` (new) | job-upsert path calls `applications.services.create_application(job_id=..., status="discovered")` as part of ingesting a new job, per the decided auto-create-application design (Section 8) | 2 |
| `domains/applications/priority.py` / `ml/application_priority/ranker.py` | add `freshness` and `new_grad_confidence` components (handoff's Priority formula includes them; current implementation doesn't) — additive fields, keep backward-compatible defaults | 3 |
| `src/swetrack/api.py` | add `/api/sources`, `/api/jobs/sync`, `/api/jobs/import` routes; existing `/jobs`, `/recommend`, `/applications*` routes stay as-is | 1–4 |
| `README.md` | document new milestones once real, following the existing "Milestone N" pattern (not before implementation, per `CLAUDE.md`) | after each checkpoint |
| `static/dashboard.html` | job inbox UI (Checkpoint 4) — additive, existing panels untouched | 4 |
| `.github/workflows/ci.yml` | none required for Checkpoints 1–3 (no live network calls in tests, per handoff Section 17) | — |

No modification is needed to `ranking/`, `readiness.py`, `skills/`, `learning/`,
or `ml/knowledge_tracing`/`study_ranking` — these are consumed, not changed.

## 6. Database/schema and migration plan

**Current state:** no migration tool. `init_db()` calls `Base.metadata.create_all`,
which is additive-only (new tables/columns on new models are picked up
automatically; it does not alter existing tables). This has been sufficient
because every prior milestone only ever added new tables, never altered one.

**Plan for Job Radar:**
1. Continue without Alembic through Checkpoint 2. `job_sources`, `jobs`
   (DB-backed), and `job_assessments` are all new tables — `create_all`
   handles them with no migration tooling needed, consistent with "minimize
   new dependencies" and the existing pattern.
2. Only introduce Alembic if a *later* checkpoint needs to alter an
   already-shipped table's schema (e.g., adding a column to `job_sources`
   after real user data exists in `var/swetrack.db`). Flag this explicitly
   when it happens rather than adding Alembic speculatively now.
3. **Naming — decided:** the handoff's `jobs` table name would collide with
   the existing concept of "a job" (`JobRecord`, the Pydantic model backing
   the CSV-sourced sample data, and `job_id` foreign keys already used by
   `applications.job_id` / `interviews`). The DB table is named
   `discovered_jobs` (ORM class `DiscoveredJobRecord`) to keep it unambiguous
   from the existing CSV-backed `JobRecord`; `swetrack.domains.jobs.schemas.NormalizedJob`
   is the adapter-output shape (matches the handoff's own `NormalizedJob` name
   for that piece).
4. **Unifying `job_id` across sources:** `applications.job_id` and
   `interviews.application_id`-linked flows are untyped strings today (no FK
   to a `jobs` table, because none exists). Once `discovered_jobs` exists,
   decide whether `ApplicationRecord.job_id` should be able to reference
   *either* a CSV `job_id` (e.g. `"JOB-003"`) or a `discovered_jobs.id`
   (UUID) — the simplest option, and the one this plan recommends, is to keep
   `job_id` as an untyped string key exactly as it is today (no FK constraint
   is enforced now either), and give discovered jobs a `canonical_key` that
   doubles as their `job_id` for application-tracking purposes. This avoids
   touching `ApplicationRecord`'s schema at all.

## 7. Integration points with existing Role Fit and Readiness systems

- Role Fit: unchanged. `Ranker.score_jobs` already accepts any `JobRecord`; a
  `discovered_jobs` row converts to a `JobRecord` (title/company/description/
  skills/location) at the service boundary in `domains/jobs/services.py`, the
  same way `config.load_jobs()` converts CSV rows today.
- Readiness: unchanged. `compute_readiness(session, job=..., profile=..., ranker=...)`
  takes a `JobRecord` — discovered jobs plug in identically to sample jobs.
- The one new integration surface is **eligibility + freshness feeding into
  Application Priority** (Section 8) — additive fields on
  `ApplicationPriorityComponents`/`ApplicationPriorityWeights`, not a rewrite.

## 8. How Role Fit, Readiness, and Application Priority stay separate

This is already the repository's architecture, not something Job Radar needs
to introduce:

- **Role Fit** = `ranker.score_jobs(...)` output — semantic/lexical
  candidate↔job similarity only. Job Radar adds no new inputs here.
- **Readiness** = mean BKT mastery across a job's canonical required skills —
  practice-history-only. Job Radar adds no new inputs here.
- **Application Priority** = a separately-weighted combination
  (`ApplicationPriorityWeights`) that already treats Role Fit and Readiness as
  two of six independent, visible components. Job Radar's freshness and
  new-grad-eligibility signals become two *additional* components in this same
  struct — `ApplicationPriorityComponents` grows, `score_application` gets two
  more weighted terms, `ApplicationPriorityWeights` gets two more fields whose
  defaults still sum to 1.0. No score is ever collapsed into another.

**Decided:** do not build a *second*, parallel "job-level priority" for
pre-application discovered jobs (handoff's `job_assessments.application_priority_score`)
that duplicates `applications/priority.py`. Instead, ingesting a job
auto-creates a `"discovered"`-status application the moment it's persisted
(this repo already models `"discovered"` as a first-class `ApplicationStatus`
literal), so every discovered job flows through the one existing
`compute_application_priority` / `rank_application_priorities` path with no
new scoring code. This means `domains/jobs/services.py`'s job-upsert path
calls `applications.services.create_application` (or an equivalent direct
insert) as part of ingesting a new job — one more concrete integration point
to add to Section 5's modification table for Checkpoint 2.

## 9. Risks, conflicts, technical debt, and open assumptions

**Risks / conflicts:**
- `applications/services.py::_job_exists` and `opportunities/config.load_jobs()`
  both assume "all jobs live in one CSV." Any checkpoint that lets a user
  create an application against a discovered job must update this check, or
  application creation will silently 422 for every real Job Radar job.
- The handoff's Application Priority formula (Section 10: `0.35 role_fit +
  0.30 freshness + 0.15 preference + 0.10 new_grad_confidence + 0.10
  evidence_coverage`) is **not** the formula already implemented (6 components,
  different weights, no freshness/new_grad_confidence/evidence_coverage yet).
  Treat the handoff's formula as a starting proposal to reconcile with the
  existing `ApplicationPriorityWeights`, not as something already built.
- `httpx` is currently a **dev-only** dependency (used by FastAPI's
  `TestClient`). Real ATS polling needs it as a runtime dependency — a small,
  low-risk `pyproject.toml` change, called out explicitly since the handoff
  says "minimize new dependencies."
- No Alembic today (Section 6) — first real migration need (schema change to
  an already-populated table) will require a decision the repo hasn't had to
  make yet.

**Technical debt already present (not introduced by Job Radar):**
- `data/sample_jobs.csv`'s `application_deadline` values are static demo
  dates that will all eventually read as "passed" (README's own admission).
- No lint/type-check tooling configured at all (`ruff`/`mypy` absent from both
  `pyproject.toml` and CI) — `CLAUDE.md`'s "run lint/type checks if
  configured" step is a no-op today; nothing to run, nothing broken.

**Decisions confirmed with the user (resolved, no longer open):**
1. DB table name: `discovered_jobs` (Section 6).
2. Discovered jobs auto-create a `"discovered"`-status application immediately
   on ingestion, reusing the existing Application Priority pipeline rather
   than building a second scoring path (Section 8).
3. Candidate eligibility fields (graduation date, work authorization, excluded
   levels, target roles) live in a new, separate `config/candidate.example.yaml`
   + small new Pydantic model, not on `CandidateProfile` (Section 3).

**Remaining open question, not yet decided — revisit before/at Checkpoint 3:**
- `applications.job_id`/`interviews` FK strategy once `discovered_jobs` exists
  (Section 6, item 4): this plan's default recommendation is to leave `job_id`
  as an untyped string and give discovered jobs a `canonical_key` that serves
  as that string, avoiding any change to `ApplicationRecord`'s schema. Flag if
  a stronger FK relationship turns out to be needed once real discovered-job
  volume makes string-matching fragile.

## 10. Dependency changes, minimizing new dependencies

| Dependency | Change | Why |
|---|---|---|
| `httpx` | move from `dev` to core `dependencies` | Already installed (dev extra); needed at runtime for ATS polling. Zero new install. |
| *(none else)* | — | `pydantic`, `SQLAlchemy`, `pandas`, `PyYAML` already cover normalization, persistence, and source-registry parsing. No new HTTP client, no new scheduler library, no LaTeX library needed until Checkpoint 5 (out of scope here). |

No new paid service, no vector database, no queue, no Alembic (Section 6), no
APScheduler — a stdlib-friendly `cron`/LaunchAgent or a manual CLI command
(`swetrack jobs sync`, as a new `scripts/jobs_sync.py`, matching the existing
`scripts/*.py` CLI pattern rather than introducing a `cli/` package) is enough
for Checkpoint 1–2 polling, per the handoff's own local-scheduler-first stance.

## 11. Tests required for upcoming work

Following the existing one-file-per-module pattern in `tests/`:

- `tests/test_job_adapters.py` — Greenhouse/Lever/Ashby payload → `NormalizedJob`
  mapping against frozen fixtures in `tests/fixtures/ats/`; no live network
  calls (mirrors handoff Section 17 and this repo's existing test style — see
  `tests/test_rankers.py` for the fixture-based pattern already in use).
- `tests/test_job_normalization.py` — title/company normalization, dedup key
  construction, tracking-parameter stripping from URLs.
- `tests/test_jobs_persistence.py` (Checkpoint 2) — idempotent upsert (sync
  twice → no duplicate row), revision handling (description change keeps
  `first_seen_at`), cross-source duplicate detection.
- `tests/test_eligibility.py` (Checkpoint 3) — positive/negative/conflicting/
  ambiguous cases from handoff Section 9; graduation-window edge cases around
  May 2026.
- Extend `tests/test_application_priority.py` (Checkpoint 3) once
  freshness/new-grad components are added, so score-composition math stays
  covered the same way it is today.
- `tests/test_api_jobs.py` (whichever checkpoint adds `/api/jobs/sync` etc.) —
  same `TestClient` pattern as `tests/test_api.py`.

All new tests must run offline and deterministically, matching the existing
suite (194/194 passing, no network access, no external services) — verified
by this checkpoint's `pytest -q` run.

## 12. Smallest useful vertical slice for Job Radar Checkpoint 1

Per the handoff's own Checkpoint 1 scope, narrowed to what's genuinely
smallest given what already exists:

1. `domains/jobs/schemas.py::NormalizedJob` (Pydantic) — the one shape every
   adapter returns.
2. `domains/jobs/adapters/base.py` — a `Protocol` with one method,
   `fetch() -> list[NormalizedJob]`.
3. `domains/jobs/adapters/greenhouse.py` — the single most standardized,
   best-documented public API of the three (handoff Section 6.1); implement
   this one adapter first, not all three at once.
4. One frozen fixture (`tests/fixtures/ats/greenhouse_sample.json`) + one test
   module proving payload → `NormalizedJob` mapping, including the
   published-vs-updated timestamp distinction the handoff insists on
   (Section 8).
5. A `scripts/jobs_fetch.py --source greenhouse --token <x> --dry-run` CLI
   that prints normalized jobs to stdout — **no database writes yet** (that's
   Checkpoint 2), matching the handoff's own Checkpoint 1 acceptance
   criterion ("`swetrack jobs sync --dry-run` prints normalized jobs without
   DB writes").

Deliberately deferred to later slices within Checkpoint 1: Lever, Ashby,
manual import, the source registry YAML, and HTTP retry/backoff — add each
once the Greenhouse path is proven, per `CLAUDE.md`'s "work milestone by
milestone" instruction. This also lets `httpx`'s move to a core dependency
(Section 10) be validated against exactly one real, documented API shape
before generalizing the adapter `Protocol`.

## 13. Discrepancies between the repository and the two project documents

| Document claim | Repository reality |
|---|---|
| "Latest project record: 130 passing tests and milestones M0–M11 complete in a 14-milestone plan" | **194 passing tests**, and the repository has completed all 15 of its own "Milestone N" units (its own numbering, distinct from `CLAUDE.md`'s M0–M10 scheme), covering `CLAUDE.md` Phases 0 through 14 plus an added Dashboard UI milestone not in the original phase list. |
| Handoff Section 15's suggested layout (`backend/app/api/`, `ingestion/`, `cli/jobs.py`, `resume/`) | Repository uses `src/swetrack/domains/*`, one `api.py`, two `scripts/*.py` CLI files, no `resume/` directory. Section 4 of this plan adapts the handoff's names to the real layout rather than forcing the suggested tree. |
| Handoff Section 10's Application Priority formula (`0.35 fit + 0.30 freshness + 0.15 preference + 0.10 new_grad_confidence + 0.10 evidence_coverage`) | A different 6-component formula already exists and is shipped (`ml/application_priority/ranker.py`) — see Section 9's open risk above. |
| Handoff Section 7's candidate config (`graduation_date`, `work_authorization`, `excluded_levels`, etc.) | No such config exists; the current `CandidateProfile` has a different, ranking-focused shape (skills/experience/preferences only). Section 6 of this plan proposes a new, separate file rather than extending `CandidateProfile`. |
| Handoff Section 7's suggested `Alembic` migrations "if already present" | Not present; `alembic` only appears as an unrelated transitive package in the dev virtualenv, not a project dependency. |
| Context doc Section 2's "Local MLflow experiment tracking" as a bullet among unverified claims | **VERIFIED** — `mlruns/` contains real, non-empty logged runs from `scripts/run_experiment.py` with recorded metrics (`ndcg_at_k`, `precision_at_k`). |
| Context doc's implication that React might be in use ("SWETrack: FastAPI, React, SQLAlchemy...") | **NOT IMPLEMENTED** — the only UI is a single static, dependency-free HTML file (`static/dashboard.html`), explicitly chosen over a frontend framework per the README. |

No resume claims, README claims, or milestone documentation were changed as
part of this checkpoint.
