# SWETrack

SWETrack is a personalized ML platform for new-grad SWE recruiting and interview
preparation, combining semantic job-role ranking with skill modeling across coding and
System Design to generate role-specific readiness gaps and prioritized study
recommendations. It started as **RoleRank** (a standalone job-ranking tool) and has since
grown into five connected product areas, all implemented in this repository, $0 to run,
fully local:

- **Opportunity Intelligence** — ranks jobs against a candidate profile (`domains/opportunities/`),
  tracks a recruiting pipeline per job (`domains/applications/`), and combines Fit + Readiness +
  freshness + eligibility + preference/compensation/deadline signals into one explainable
  Application Priority score.
- **Interview Tracking** — logs interview rounds and feeds decided outcomes back into skill
  mastery (`domains/interviews/`).
- **Skill Intelligence** — a canonical software-engineering skill taxonomy with deterministic
  alias normalization (`domains/skills/`), and Bayesian Knowledge Tracing over immutable
  `SkillEvent` history to estimate per-skill mastery (`domains/learning/`, `ml/knowledge_tracing/`).
- **Adaptive Preparation** — an explainable heuristic ranker recommending what to study next from
  mastery gaps, staleness, difficulty fit, and repetition (`ml/study_ranking/`).
- **Job Radar** — polls public ATS boards (Greenhouse/Lever/Ashby) and manual imports for new
  postings, deduplicates them, classifies new-grad eligibility, scores freshness, surfaces a job
  inbox with local notifications, and generates truth-gated, evidence-backed one-page tailored
  resumes (`domains/jobs/`, `domains/resume/`). See [Job Radar](#job-radar) below.

Not a deployed product and not a system that has learned from real user behavior — every ML
component here is either an unsupervised/deterministic baseline or a configured (not fit/learned)
probabilistic model, evaluated against synthetic or small hand-curated data. See each section's
"Honest interpretation" for what a given result does and does not demonstrate.

## Product loop

```text
Jobs → Role Ranking → Skill Requirements → Readiness Gap → Study Recommendations
  → Practice (coding / System Design) → Interview → Skill Updates → (back to Readiness Gap)
```

Once a job becomes a tracked application, Application Priority re-weights Role Fit and
Readiness alongside preference, company, compensation, and deadline signals — a separate,
visible score from Readiness, never blended into it (CLAUDE.md: "Never conflate them").

## Opportunity Intelligence: the ranking problem

New-grad applicants review many postings with inconsistent titles and long descriptions.
Keyword search can miss semantically relevant jobs, while generic job boards do not
understand an individual candidate's technical background or role preferences. SWETrack's
Opportunity Intelligence subsystem ranks a supplied set of software-engineering jobs
against a supplied candidate profile and explains the most visible matching signals.

Opportunity Intelligence's job ranking is currently an **unsupervised content-based
retrieval/ranking system**. It is not collaborative filtering, not a supervised model
trained on user feedback, and its similarity scores are not probabilities of getting an
interview.

## Architecture

```text
swetrack/
├── config/
│   └── candidate_profile.example.yaml   # example, non-sensitive profile
├── data/
│   ├── sample_jobs.csv                  # 26 sample/synthetic job postings
│   └── relevance_labels.csv             # manually curated 0/1/2 relevance labels
├── examples/
│   └── recommend_request.json           # sample POST /recommend body
├── src/swetrack/
│   ├── api.py                           # FastAPI app: every endpoint below
│   ├── domains/
│   │   ├── opportunities/               # Opportunity Intelligence (formerly RoleRank)
│   │   │   ├── config.py                # YAML/CSV loading + validation
│   │   │   ├── models.py                # Pydantic schemas (candidate, job, API I/O)
│   │   │   ├── preprocessing.py         # text normalization + document construction
│   │   │   ├── evaluation.py            # Precision@K, NDCG@K
│   │   │   ├── readiness.py             # Role Fit + Readiness (skill-gap-aware)
│   │   │   └── ranking/
│   │   │       ├── base.py              # shared Ranker interface, sorting, explanations
│   │   │       ├── tfidf.py             # TfidfRanker (lexical baseline)
│   │   │       └── embeddings.py        # EmbeddingRanker (sentence-transformers)
│   │   ├── applications/                # recruiting pipeline + Application Priority
│   │   │   ├── models.py / schemas.py / services.py
│   │   │   └── priority.py              # Fit + Readiness + preference/comp/deadline
│   │   ├── interviews/                  # interview rounds, feeding decided outcomes to mastery
│   │   ├── skills/                      # canonical taxonomy + deterministic alias normalization
│   │   ├── learning/                    # activities, immutable attempts/SkillEvents, mastery cache
│   │   ├── jobs/                        # Job Radar: ingestion, persistence, eligibility, inbox
│   │   │   ├── adapters/                # greenhouse.py / lever.py / ashby.py / manual.py
│   │   │   ├── models.py                # DiscoveredJobRecord (discovered_jobs table)
│   │   │   ├── services.py              # sync_source: idempotent upsert + cross-source dedup
│   │   │   ├── eligibility.py           # deterministic new-grad classifier
│   │   │   ├── freshness.py             # 0-1 decay score from published/first-seen time
│   │   │   ├── notifications.py         # dedup + threshold + quiet hours -> macOS notification
│   │   │   ├── registry.py              # source registry YAML loading + adapter construction
│   │   │   └── inbox.py                 # enriched, filterable job inbox
│   │   └── resume/                      # Job Radar: evidence library + tailoring
│   │       ├── parser.py                # LaTeX resume -> draft evidence items
│   │       ├── evidence.py              # evidence.yaml loading + validation
│   │       ├── tailoring.py             # skill-match scoring, selection, gaps, ATS coverage, diff
│   │       ├── truth_gate.py            # rejects any unverified/disabled/unknown evidence
│   │       └── latex.py                 # renders + compiles a one-page tailored PDF
│   ├── ml/
│   │   ├── knowledge_tracing/bkt.py     # Bayesian Knowledge Tracing (pure functions)
│   │   ├── study_ranking/ranker.py      # Adaptive Preparation heuristic ranker
│   │   ├── application_priority/ranker.py  # Application Priority heuristic ranker
│   │   └── evaluation/                  # BKT and eligibility-classifier baselines
│   ├── infrastructure/
│   │   ├── database/                    # SQLAlchemy engine/session, SQLite by default
│   │   ├── notifications/macos.py       # osascript-based local notifications
│   │   └── paths.py                     # repo-root resolution
│   └── static/dashboard.html            # dashboard UI, incl. the Job Radar inbox panel
├── resume/
│   ├── evidence.yaml                    # tracked: structured resume facts, no contact info
│   ├── master_resume.tex                # gitignored: real resume, has personal contact info
│   └── variants/                        # gitignored: generated tailored .tex/.pdf per job
├── scripts/
│   ├── recommend.py                          # CLI: rank sample jobs, print top K
│   ├── run_experiment.py                     # run both rankers, log to MLflow
│   ├── run_knowledge_tracing_experiment.py   # BKT vs. baseline on a synthetic learner
│   ├── run_eligibility_evaluation.py         # eligibility classifier vs. a labeled fixture
│   ├── jobs_fetch.py                         # dry-run or persist a sync from one/all sources
│   ├── jobs_sync_and_notify.py               # sync + notify; what the LaunchAgent runs
│   ├── install_launch_agent.py / uninstall_launch_agent.py
│   ├── parse_resume_to_evidence.py           # bootstrap/refresh the evidence library
│   └── tailor_resume.py                      # generate a truth-gated tailored resume PDF
├── tests/                               # pytest: one file per domain/ML module + API
├── Dockerfile / .dockerignore
└── mlruns/                              # generated locally by run_experiment.py; gitignored
```

Both rankers implement one `Ranker` interface (`score_jobs` → sort, deterministic
job-ID tie-break, top-K truncation, and structured explanations are handled once in
`ranking/base.py`), so they stay directly comparable.

A modular monolith, not microservices: domains are closely related (Opportunities feeds
Applications feeds Priority; Skills/Learning feed both Readiness and Adaptive Preparation),
deployment complexity would buy nothing at this scale, and Python-level module boundaries
already give the separation that matters — each domain owns its own models/schemas/services,
`ml/` stays free of database or business-logic imports, and every read/write to a domain's
tables goes through that domain's `services.py`.

**Candidate text** is built from named sections: `skills`, `experience`,
`preferred roles`, `interests`. **Job text** is built from `title`, `description`,
`skills`, `experience level`. Company, location, and other attributes are never folded
into the ranked text; location is only used for structured match explanations.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest -q
```

Rank the sample jobs against the example candidate profile:

```bash
python scripts/recommend.py --ranker tfidf --top-k 5
python scripts/recommend.py --ranker embedding --top-k 5   # first run downloads the free local model
```

Run the offline experiment (both rankers, logged to a local MLflow file store):

```bash
python scripts/run_experiment.py --k 5
```

Serve the API:

```bash
uvicorn swetrack.api:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000/** in a browser for the dashboard UI (Milestone 15, below), or
**http://127.0.0.1:8000/docs** for the auto-generated interactive Swagger UI covering every
endpoint.

In another terminal:

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/recommend -H "Content-Type: application/json" --data @examples/recommend_request.json
```

On Windows PowerShell:

```powershell
curl.exe http://127.0.0.1:8000/health
curl.exe -X POST http://127.0.0.1:8000/recommend -H "Content-Type: application/json" --data "@examples/recommend_request.json"
```

## API

All endpoints, grouped by domain — full detail (request/response shape, edge cases) is in each
domain's own section further below:

| Domain | Endpoints |
|---|---|
| Core | `GET /health`, `GET /jobs`, `POST /recommend` (both now include Job Radar discovered jobs) |
| Job Radar inbox | `GET /jobs/inbox` |
| Readiness | `GET /opportunities/{job_id}/readiness` |
| Applications | `POST /applications`, `GET /applications`, `GET /applications/{id}`, `POST /applications/{id}/status`, `GET /applications/{id}/history` |
| Application Priority | `GET /applications/{id}/priority`, `GET /applications/priority` |
| Interviews | `POST /interviews`, `GET /interviews`, `GET /interviews/{id}` |
| Skill mastery | `GET /mastery`, `GET /mastery/summary`, `GET /recommendations` |
| Dashboard | `GET /` (HTML, not JSON — see Milestone 15 below) |

Job discovery/sync, resume evidence, and resume tailoring are CLI-only for now
(`scripts/jobs_fetch.py`, `scripts/jobs_sync_and_notify.py`, `scripts/tailor_resume.py`) —
see [Job Radar](#job-radar).

- `GET /health` — service status and version. Never loads the sentence-embedding model.
- `GET /jobs` — sample job metadata, with optional `?limit=&offset=` pagination.
- `POST /recommend` — ranks jobs against a candidate profile.

`POST /recommend` never silently substitutes a private resume. Either supply `profile`
directly, or explicitly opt into the checked-in example profile with
`"use_example_profile": true`:

```json
{
  "use_example_profile": true,
  "ranker": "tfidf",
  "top_k": 5
}
```

Sample response (truncated to one result):

```json
{
  "ranker": "tfidf",
  "top_k": 5,
  "results": [
    {
      "rank": 1,
      "job": {
        "job_id": "JOB-003",
        "company": "CloudForge Labs",
        "title": "Full Stack Software Engineer - New Grad",
        "location": "Remote",
        "skills": ["Python", "FastAPI", "React", "AWS", "Docker", "CI/CD", "Git"],
        "experience_level": "New graduate",
        "source": "synthetic"
      },
      "ranker": "tfidf",
      "score": 0.25091064589057305,
      "reasons": [
        "Matched skills: Python, AWS, Git, Docker, FastAPI",
        "Preferred role match: Software Engineer, Full Stack Engineer",
        "Preferred location match: Remote"
      ]
    }
  ]
}
```

Invalid `ranker`, non-positive `top_k`, `top_k` greater than the available job count, a
malformed profile, or an omitted profile with `use_example_profile` unset all return a
`422` with a clear error message.

Similarity scores are relative signals for ranking, not calibrated probabilities and not
a claim that a candidate will receive an interview.

## Experiment results

Measured by running `python scripts/run_experiment.py --k 5` against the checked-in
26-job sample dataset and its manually curated relevance labels:

| Ranker    | Precision@5 | NDCG@5 | MLflow run ID                      |
|-----------|-------------|--------|-------------------------------------|
| TF-IDF    | 1.0000      | 1.0000 | `00686e24e08349c28c6b8a0c5b1dcdda`  |
| Embedding | 1.0000      | 1.0000 | `06cf27e13c834de39167efcbef7a5813`  |

**Honest interpretation:** both rankers tie at Precision@5 = 1.0 and NDCG@5 = 1.0. The
top 5 jobs returned by both rankers all carry the strongest relevance label (2) in
`data/relevance_labels.csv`. This is not a fabricated or cherry-picked result — the
sample dataset has 10 clearly-worded, strongly-relevant entry-level backend/full-stack
postings that share exact technical vocabulary (Python, AWS, REST APIs, Docker) with the
example profile, so a lexical baseline is already strong here and there is no room for
either ranker to separate at K=5. An embedding model outperforming TF-IDF is not
guaranteed, and this run shows a tie rather than a win for either approach. The two
rankers do produce different orderings within the top 5 (compare the CLI outputs above),
reflecting TF-IDF's exact-term weighting versus the embedding model's semantic
similarity — the tie is in the *evaluation metric*, not in the raw output.

This is evaluation plumbing validated on a tiny, single-profile demonstration set, not
evidence that either ranker generalizes to a larger or different candidate population.

## Skill taxonomy (Milestone 4)

A canonical software-engineering skill graph shared across resumes, job postings, coding
practice, System Design, and interviews (CLAUDE.md Phase 4). See `src/swetrack/domains/skills/`.

- `taxonomy.py` — 37 skills across 8 categories (`programming_languages`, `algorithms`,
  `data_structures`, `backend`, `data_systems`, `distributed_systems`, `reliability`,
  `system_design`), each with `id`/`slug`/`name`/`category`/`parent_id`/`aliases`.
- `normalization.py` — `normalize_skill(raw_text)` maps free-text strings ("DynamoDB", "Amazon
  DynamoDB", "DP") to one canonical `Skill` via case-insensitive, whitespace-normalized exact
  matching against each skill's name, slug, and aliases. Deterministic, not embedding-based —
  CLAUDE.md Phase 4 is explicit that fuzzy/embedding matching is unnecessary here. An
  unrecognized term returns `None` rather than a guessed match.

No API endpoint yet — consumed internally by `opportunities.readiness.required_skill_ids` (maps
a job's free-text `skills` to canonical ids) and `learning.services.create_activity` (validates
an activity's `skill_ids`).

## Learning event foundation (Milestone 5)

Immutable, replayable observations of skill practice, decoupled from any specific mastery
model (CLAUDE.md Phase 6). See `src/swetrack/domains/learning/`.

- `LearningActivityRecord` — a practiceable activity (`slug`, `title`, `activity_type`,
  `skill_ids`, optional `difficulty`), validated against the skill taxonomy at creation.
- `AttemptRecord` — one practice attempt against an activity (`success`, `notes`, `timestamp`).
- `SkillEventRecord` — one immutable observation per skill an attempt exercised: `skill_id`,
  `source_type` (`coding_attempt` / `system_design_attempt` / `interview_feedback` /
  `concept_review`), `source_id`, `outcome` (`[0, 1]`), `evidence_weight`. Never updated or
  deleted by `services.py`, only ever inserted, so mastery can always be recomputed from
  scratch by replaying this table if the mastery model changes.

No API endpoint yet — this is the shared persistence layer Milestones 6-9 (BKT, coding
practice, System Design practice, study recommendations) are all built on.

## Knowledge tracing (Milestone 6, synthetic demonstration)

There is no real multi-attempt learner history yet — the learning domain (activities,
attempts, immutable `SkillEvent`s) was only introduced in Milestone 5. `scripts/run_knowledge_tracing_experiment.py`
demonstrates the Bayesian Knowledge Tracing (BKT) mastery model against a deterministically
seeded, clearly synthetic learner simulation, not real usage:

```bash
python scripts/run_knowledge_tracing_experiment.py
```

Example output (seed=42, 40 simulated opportunities):

```text
Model                             Brier score     Log loss
BKT (default parameters)               0.1069       0.3530
Historical success rate                0.1380       1.3056

BKT scored lower Brier loss than the naive baseline on this run.
```

**Honest interpretation:** BKT's configured (not fit/learned) default parameters
(`P(L0)=0.3, P(T)=0.1, P(G)=0.2, P(S)=0.1`) beat the naive "historical success rate so
far" baseline on this one synthetic run — both by Brier score and, more sharply, by log
loss. The naive baseline's log loss is dominated by early overconfidence: after a single
early correct observation its estimate jumps to exactly 1.0, and any later miss is scored
harshly. BKT's guess/slip terms keep its estimate away from the extremes, which is exactly
the calibration behavior BKT is intended to provide. This is one run against a simulated
learner with hand-picked "true" parameters different from BKT's defaults — it demonstrates
the evaluation harness works, not that BKT will outperform the baseline on real interview
practice data.

## Coding practice (Milestone 7)

Structured LeetCode-style practice attempts, feeding one SkillEvent + BKT mastery update per
skill the activity exercises (CLAUDE.md Phase 7). See `learning.services.record_coding_attempt`.

- Records `hints_used`, `confidence`, `mistake_type`, `duration_seconds` in a
  `CodingAttemptRecord` alongside the shared `AttemptRecord`/`SkillEventRecord` writes.
- `mistake_type` (one of `algorithm_selection`, `state_definition`, `recurrence`, `off_by_one`,
  `pointer_management`, `base_case`, `complexity`, `data_structure_choice`, `mutation`,
  `edge_case`) must be `None` on a successful attempt — nothing to categorize as a mistake.
- No automatic code analysis: CLAUDE.md Phase 7 is explicit that manual structured data is
  acceptable, often higher quality, and a required LLM/static-analysis dependency is out of
  scope for this milestone.

No API endpoint yet — service-layer + tests (`tests/test_coding_practice.py`) only.

## System Design practice (Milestone 8)

Per-skill rubric scoring, so one design session can update several skills by different amounts
rather than one uniform pass/fail (CLAUDE.md Phase 8). See
`learning.services.record_system_design_attempt`.

- `scores: dict[skill_id, float]` must cover exactly the activity's `skill_ids` — each score
  becomes that skill's `SkillEvent.outcome` (full rubric fidelity preserved) and, via a 0.5
  threshold, one BKT mastery step.
- The Attempt's overall `success` is the mean score meeting that same threshold — a documented
  simplification, since `AttemptRecord.success` is one boolean shared by every activity type.
- Manual rubric entry is the baseline; CLAUDE.md Phase 8 explicitly rules out a paid LLM
  evaluator as a dependency.

No API endpoint yet — service-layer + tests (`tests/test_system_design_practice.py`) only.

## Adaptive study recommendations (Milestone 9)

A deterministic, explainable heuristic ranker over practiceable activities — not a learned
recommender (CLAUDE.md Phase 10). See `ml/study_ranking/ranker.py` and
`learning.services.get_study_recommendations`.

- Components, each in `[0, 1]`: `mastery_gap` (`1 - mastery`, from cached BKT mastery),
  `staleness` (exponential decay since the skill's mastery was last updated, half-life 14 days),
  `difficulty_fit` (how well an activity's declared difficulty suits the current mastery gap —
  easy activities score best when a skill is nearly unmastered, hard when nearly mastered), and
  `repetition_penalty` (this activity's own attempts in the last 7 days).
- Default weights: `mastery_gap` 0.45, `staleness` 0.30, `difficulty_fit` 0.25 (sum to 1.0), and
  `repetition_penalty` 0.2 as a separate subtractive term.
- An activity with multiple skills uses the mean component across them. An optional `skill_ids`
  filter restricts ranking to activities touching at least one given skill — used by Role
  Readiness (below) to surface only recommendations relevant to one job's required skills.

- `GET /recommendations?top_k=` — this ranker over every skill any tracked activity touches, not
  filtered to one job (see Milestone 14 below for the endpoint). `GET /opportunities/{id}/readiness`
  also surfaces it, filtered to one job's required skills.

## Role Readiness (Milestone 10)

CLAUDE.md Phase 11's flagship integration: connects a job's skill requirements to the
candidate's tracked mastery, kept as a score deliberately separate from Role Fit (CLAUDE.md:
"Never conflate them" — Fit is candidate↔job alignment, Readiness is preparation for the
skills a job requires). See `src/swetrack/domains/opportunities/readiness.py`.

- `GET /opportunities/{job_id}/readiness?ranker=tfidf|embedding` — `fit_score` (from the chosen
  ranker, unchanged), `readiness_score` (mean tracked mastery across the job's canonical
  required skills), `skill_gaps` (per-skill `required`/`mastery`/`gap`), and up to 3
  `recommended_activities` filtered to those required skills.
- `required_skill_ids(job)` maps a job's free-text `skills` through `skills.normalization` to
  canonical ids, dropping unrecognized terms rather than guessing. Every recognized skill is
  treated as required at full importance (1.0) — job postings carry no per-skill weighting
  signal, and inventing one would be exactly the fabricated precision CLAUDE.md warns against.
- A skill with no recorded practice history uses BKT's `p_init` (0.3) as its mastery — the same
  "no history yet" default `get_study_recommendations` uses. A job with no recognized required
  skills reports `readiness_score = 1.0` (nothing to be unprepared for).

## Application pipeline (Milestone 11)

Tracks a candidate's recruiting pipeline per job — no ML, plain persisted state with an
immutable status history. See `src/swetrack/domains/applications/`.

- `POST /applications` — start tracking a `job_id` (must match a known job), at an optional
  initial `status` (default `"discovered"`).
- `GET /applications` — list tracked applications, optionally filtered by `status` and/or
  `job_id`.
- `GET /applications/{id}` — one application's current status.
- `POST /applications/{id}/status` — append a new status transition. There is no enforced
  transition graph: any `status` is reachable from any other, since real recruiting pipelines
  are not strictly linear (e.g. a rejected application can later become `interested` again for
  a different role).
- `GET /applications/{id}/history` — the full, chronological, immutable transition history.

Valid `status` values: `discovered`, `interested`, `applied`, `oa`, `recruiter_screen`,
`technical`, `system_design`, `behavioral`, `final`, `offer`, `rejected`, `withdrawn`.

This milestone intentionally adds no ranking, scoring, or prediction — CLAUDE.md's Phase 12
guidance is explicit that application-outcome ML should wait until enough real pipeline data
exists. `Application Priority` (combining Role Fit, Readiness, and pipeline signals) is future
work, not implemented here.

## Interview tracking (Milestone 12)

Logs interview rounds and, when a round's outcome is already known, feeds it into the same
skill-mastery machinery coding and System Design attempts use. See
`src/swetrack/domains/interviews/`.

- `POST /interviews` — log one round: `company`, `role`, `round_type`, `date`, `skills_tested`,
  and an optional `application_id`, `notes`, `feedback`. `result` defaults to `"pending"`.
- `GET /interviews` — list logged interviews, optionally filtered by `application_id` and/or
  `round_type`.
- `GET /interviews/{id}` — one interview.

Valid `round_type` values: `recruiter`, `oa`, `coding`, `system_design`, `behavioral`,
`hiring_manager`, `final`.

When `result` is `"passed"` or `"failed"`, one immutable `SkillEvent` (source type
`interview_feedback`, per CLAUDE.md Phase 6) and one sequential BKT mastery update is written per
skill in `skills_tested`, reusing `learning.services.apply_sequential_mastery_update` — the same
function coding and System Design attempts call. A `"pending"` result writes nothing to skill
history: CLAUDE.md Phase 13 is explicit that mastery should not be inferred before a real outcome
is known, and there is no endpoint to revise a `"pending"` result after the fact in this
milestone — logging an interview once its outcome is known is the supported path.

## Application Priority (Milestone 13)

Combines Role Fit, Readiness, preference match, company interest, compensation fit, and deadline
urgency into one explainable, component-visible score per tracked application (CLAUDE.md Phase
14) — all six components from CLAUDE.md's list, location folded into `user_preference` alongside
role. See `src/swetrack/domains/applications/priority.py` and
`src/swetrack/ml/application_priority/`.

- `GET /applications/{id}/priority` — every component, the combined `score`, and the full nested
  `readiness` result (skill gaps, recommended activities) it was derived from. Accepts the same
  `ranker` query parameter as `GET /opportunities/{id}/readiness`.
- `GET /applications/priority` — every tracked application ranked by `score`, highest first (the
  "Top Opportunities" list from CLAUDE.md's product end-state). Optional `status` filter, `top_k`
  (default 10), and the same `ranker` parameter. Registered ahead of
  `GET /applications/{id}` in `api.py` so `"priority"` is never matched as an `application_id`.

Each component is backed by a real, collected data source, never an invented number:

- `role_fit`, `readiness` — from the existing `compute_readiness` (Milestone 10), unchanged.
- `user_preference` — role/location overlap between `CandidateProfile` and the job, reusing
  `build_match_reasons`.
- `company_interest` — the same match/neutral/no-match logic as `user_preference`, against a new
  `CandidateProfile.preferred_companies` list.
- `compensation_fit` — whether `JobRecord.compensation_max` clears a new
  `CandidateProfile.minimum_compensation`; neutral (`0.5`) if either side has no data to compare.
- `deadline_urgency` — an exponential decay toward 1.0 as `JobRecord.application_deadline`
  approaches, `0.0` once it has passed or is unknown.

`data/sample_jobs.csv` now carries `compensation_min`, `compensation_max`, and
`application_deadline` for all 26 seed jobs, and `config/candidate_profile.example.yaml` carries
`preferred_companies` and `minimum_compensation` — synthetic values chosen to exercise every
component, not observed real postings. Deadlines are static demo dates and will eventually all
read as "passed" (`deadline_urgency` → 0) as real time moves past them; regenerate them
periodically rather than treating them as live data.

## Skill mastery overview (Milestone 14)

Three endpoints exposing the learning domain's mastery data directly, rather than only
indirectly through Role Readiness — built to unblock a dashboard UI needing a global "Weakest
Skills" / "Interview Readiness" view, not just a per-job one. See
`learning.services.list_mastery` / `get_interview_readiness_summary` and
`src/swetrack/domains/learning/schemas.py`.

- `GET /mastery?top_k=&category=` — every canonical taxonomy skill's mastery, weakest first.
  Optional `category` filter (one of the 8 taxonomy categories) and `top_k` cap. Every skill is
  included, not just practiced ones — an unpracticed skill defaults to BKT's `p_init` (0.3) with
  `has_history: false`, so a skill nobody has touched yet can still surface as the weakest,
  rather than silently vanishing from the list. `has_history` is what keeps that default honest:
  callers can tell a real observed estimate from a starting assumption.
- `GET /mastery/summary` — mastery averaged per skill category (`by_category`), plus a coarse
  `coding` / `system_design` rollup (the "Interview Readiness: Coding 78% / System Design 63%"
  panel from CLAUDE.md's product mockup). The two-bucket split (`programming_languages` +
  `algorithms` + `data_structures` → `coding`; `backend` + `data_systems` +
  `distributed_systems` + `reliability` + `system_design` → `system_design`) is a deliberate
  editorial grouping of the 8 real taxonomy categories, not a derived or learned one — flagged
  in code as a coarse simplification to revisit (e.g. aggregating by which activity's
  `activity_type` produced each SkillEvent, instead of by static skill category) if it proves
  too coarse once there's real multi-skill practice history to test it against.
- `GET /recommendations?top_k=` — `get_study_recommendations` with no job filter, already
  documented under Milestone 9 above; this is just its own endpoint instead of only being
  reachable through `GET /opportunities/{id}/readiness`.

Route path names (`/mastery`, `/recommendations`) match CLAUDE.md's own "API Philosophy"
section, which names both as anticipated top-level resources.

## Dashboard UI (Milestone 15)

A single static, dependency-free HTML page (`src/swetrack/static/dashboard.html`) rendering
CLAUDE.md's product end-state mockup, served at `GET /` by the same FastAPI app — same-origin
fetches to the API below it, so no CORS middleware, build step, or frontend framework is
needed.

- **Discover Jobs** — `POST /recommend` against the example profile; each result gets a
  **Track** button that calls `POST /applications`, then refreshes Top Opportunities.
  Already-tracked jobs (cross-checked against `GET /applications`) show as disabled/"Tracked"
  rather than letting you track the same job twice.
- **Top Opportunities** — `GET /applications/priority`, with the `score` and every component
  (`role_fit`, `readiness`, `user_preference`, `compensation_fit`, `deadline_urgency`) visible
  per application, never collapsed into one opaque number. Each row has a status dropdown +
  **Update status** button calling `POST /applications/{id}/status`.
- **Interview Readiness** — `GET /mastery/summary`'s `coding`/`system_design` rollup.
- **Weakest Skills** — `GET /mastery?top_k=5`, flagging `has_history: false` skills as "(no
  practice yet)" rather than presenting a default as if it were an observed estimate.
- **Today's Preparation** — `GET /recommendations?top_k=3`, with a "Reason" line naming each
  recommendation's highest-weighted component (e.g. "highest-weighted factor is mastery gap
  (72%)") — derived directly from the real returned components, not generated prose.
- **Log Interview** — a form (`company`, `role`, `round_type`, `date`, comma-separated
  `skills_tested`, `result`) calling `POST /interviews`, plus a list of logged interviews via
  `GET /interviews`. `skills_tested` takes raw canonical skill ids (e.g. `graphs, python`) --
  no autocomplete against the taxonomy yet, so an unrecognized id surfaces the API's 422
  directly rather than being silently dropped.

Every panel has its own empty state (e.g. "No tracked applications yet") and error state (e.g.
"is the API running?") rather than failing silently or showing a blank card; every write path
(track, update status, log interview) reports failures via a plain `alert()` rather than
failing silently. No build tooling, no npm, no CDN dependency — plain HTML/CSS/`fetch()` in one
file, consistent with CLAUDE.md's cost stance and its explicit caution against a "complex
frontend redesign."

## Job Radar

Job Radar extends Opportunity Intelligence from "rank a supplied set of jobs" to "find new
postings yourself, decide if they're worth acting on, and prepare a truthful resume for the
best ones" — still $0, still fully local. Built across its own five checkpoints
(`docs/job-radar-integration-plan.md` has the full Checkpoint 0 audit and decision record);
CLI-only for now, no dashboard/API wiring yet beyond the inbox endpoint below.

### Discovery and persistence (`domains/jobs/`)

- **Adapters** (`adapters/greenhouse.py`, `lever.py`, `ashby.py`, `manual.py`) fetch from each
  ATS's public, unauthenticated JSON API (or take a pasted URL/JD for `manual`) and normalize
  every source into one `NormalizedJob` shape. A shared `http_get_json`/`parse_iso_timestamp`
  helper in `adapters/base.py` avoids repeating HTTP/timestamp-parsing logic per adapter.
- **`config/sources.example.yaml`** + `registry.py` validate which boards to poll and construct
  the matching adapter; a company's identifier field (`token`/`site`/`board_name`) is enforced to
  match its declared `adapter`.
- **`services.py::sync_source`** is the only write path to the `discovered_jobs` table:
  idempotent upsert keyed by `{source_type}:{source_job_id}` (re-syncing the same job never
  duplicates it), revision detection (a changed description updates the existing row and bumps
  `last_seen_at` without touching `first_seen_at`), and cross-source duplicate detection (same
  normalized company+title+location *and* either a matching URL or near-identical description —
  flagged via `duplicate_of_id`, not merged into one row). A new, non-duplicate job immediately
  auto-creates a `"discovered"`-status `ApplicationRecord`, so it flows through the *existing*
  Application Priority pipeline unchanged rather than needing a second scoring path.
- **`to_job_record`/`list_discovered_job_records`** convert persisted discovered jobs into the
  same `JobRecord` shape the CSV sample jobs use, so `GET /jobs`, `POST /recommend`,
  `GET /opportunities/{id}/readiness`, and both priority endpoints see real discovered jobs
  automatically, with no ranking-code changes. `JobRecord.source` gained a `"discovered"` value
  (alongside `sample`/`synthetic`) so provenance stays honest.
- `scripts/jobs_fetch.py --registry` (or `--source greenhouse --token ... --company ...`) —
  `--dry-run` prints normalized jobs with no DB writes; without it, syncs for real.

### Eligibility, freshness, and priority (`domains/jobs/eligibility.py`, `freshness.py`)

- A **deterministic new-grad eligibility classifier** — `eligible`/`uncertain`/`ineligible` with
  confidence, matched phrases, and reasons, never an LLM call. Evaluated against a 30-example
  reviewed, hand-labeled fixture (`data/eligibility_labels.csv`) via
  `scripts/run_eligibility_evaluation.py`: **93% accuracy** (28/30), with both misses honestly
  reported (a wide experience range like "1-10 years" or a range next to a "senior scope" mention
  fools the regex's naive number extraction — a documented limitation, not hidden).
- **Freshness** — the handoff's 0-2h/2-6h/.../7-day decay table, `[0,1]`-scaled, from
  `source_published_at` (preferred) or `first_seen_at` ("first found").
- **Application Priority grew two real components** (`priority-v2`): `freshness` and
  `new_grad_confidence` (the eligibility confidence, inverted for a confidently-*ineligible* job
  so a clearly senior/intern posting scores low here, not high). Weights were rebalanced across
  all eight components, still summing to 1.0. `evidence_coverage` from the original handoff
  formula is deliberately *not* added — there's no resume evidence library consumer for it at the
  application-priority layer yet.

### Job inbox and notifications (`domains/jobs/inbox.py`, `notifications.py`)

- **`GET /jobs/inbox`** — every non-duplicate discovered job enriched with eligibility, priority,
  and application status, filterable by `eligibility_status`, `application_status`,
  `min_priority`, `since_hours`. Every entry keeps `source_published_at` ("published") and
  `first_seen_at` ("first found") as two separate fields, never conflated. Dashboard panel:
  **Job Radar Inbox**, with Save/Mark Applied/Dismiss buttons that just call the existing
  `POST /applications/{id}/status` (dismiss reuses the `"withdrawn"` status with an optional
  reason) — no new status values or endpoints needed.
- **macOS notifications** (`infrastructure/notifications/macos.py`) via `osascript` — no
  dependency, no-op (never raises) off-macOS. `notify_new_discoveries` dedups via a
  `DiscoveredJobRecord.notified_at` timestamp set only on an actually-sent notification, so a
  re-run never re-notifies; a configurable priority threshold and quiet-hours window
  (`QuietHours`, wraps past midnight) suppress the rest.
- `scripts/jobs_sync_and_notify.py` is the one command a LaunchAgent runs periodically (uses
  `TfidfRanker`, never triggering an embedding-model download in the background);
  `scripts/install_launch_agent.py` / `uninstall_launch_agent.py` manage a per-user
  `~/Library/LaunchAgents` plist (no root required).

### Resume evidence and tailoring (`domains/resume/`)

- **`resume/evidence.yaml`** (tracked) holds structured resume facts — no personal contact
  info — parsed automatically from a real `resume/master_resume.tex` (gitignored: it has a phone
  number and email) by a purpose-built LaTeX parser (`parser.py`) that correctly handles this
  template's nested formatting (e.g. `\textit{Role \textbf{--} More role}`) via a proper
  balanced-brace matcher, not a naive regex. `scripts/parse_resume_to_evidence.py` (re)generates
  the draft for review; nothing is trusted blindly — every item defaults to `verified: true` but
  can be flagged `verified: false` / `enabled: false` with a `review_note` when a claim no longer
  matches reality.
- **Deterministic tailoring** (`tailoring.py`) — case-insensitive skill-overlap scoring reorders
  bullets *within* each employer/project block by relevance to one job (never reordering
  employers themselves), and produces a gaps report (job-required skills with no supporting
  evidence — never added to the resume) and an ATS coverage report (covered vs. unsupported
  keywords, never an "ATS pass probability").
- **Truth gate** (`truth_gate.py`) rejects any selection referencing an unknown, disabled, or
  unverified evidence item. Every included bullet renders as its evidence item's text verbatim —
  no keyword substitution or wording variants — so no metric, date, or employer can ever change
  from what's in `evidence.yaml`.
- **LaTeX rendering + PDF compilation** (`latex.py`) copies the header/Education/Technical Skills
  sections verbatim from the original template and only rebuilds Experience/Projects bullets from
  selected evidence (plain text, no bold reconstruction, so nothing can drift from the
  truth-gate-verified text); compiles via `pdflatex` and validates page count/text extraction with
  `pypdf`. `scripts/tailor_resume.py --job-id <id>` runs the full pipeline end-to-end for any
  sample or discovered job.
- Requires a local LaTeX distribution (e.g. BasicTeX via Homebrew, plus `enumitem`, `titlesec`,
  `cm-super`, etc. via `tlmgr` — BasicTeX ships without them) to actually compile a PDF; without
  one, everything through LaTeX source generation still works, just without the final PDF step.

## Docker

```bash
docker build -t swetrack:milestone-1 .
docker run --rm -p 8000:8000 swetrack:milestone-1
```

Then, from the host:

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/recommend -H "Content-Type: application/json" --data @examples/recommend_request.json
```

The image installs `sentence-transformers`/`torch` (a declared runtime dependency for the
embedding ranker) but does **not** pre-download the `all-MiniLM-L6-v2` model weights at
build time — `GET /health` and TF-IDF requests never touch the model. The first
`ranker="embedding"` request inside a running container downloads the weights from
Hugging Face into `/root/.cache/huggingface`, which is lost when the container is
removed. To persist/reuse that cache across runs, mount a volume:

```bash
docker run --rm -p 8000:8000 -v swetrack-hf-cache:/root/.cache/huggingface swetrack:milestone-1
```

> Verified: `docker build` and `docker run` were executed end-to-end (Docker Desktop 28.3.3) —
> `GET /health`, `GET /jobs`, `POST /applications`, `GET /applications/priority`, and `GET /`
> (the dashboard UI) all returned correct responses against the running container, including a
> fresh SQLite DB created inside the container on first write. `GET /` specifically confirms
> the dashboard's file path resolves correctly under a non-editable `pip install` (it's
> resolved via `find_repo_root()` + `SWETRACK_ROOT_DIR`, not `Path(__file__)` — the same fix
> `data`/`config` already needed, since `Path(__file__)` would otherwise point into
> `site-packages` instead of the copied `src/` tree). Re-run this check after any change to
> `Dockerfile`, `pyproject.toml`, or `infrastructure/database/`, since none of those are
> covered by `pytest`.

## Cost stance

Everything across every milestone runs locally and costs $0: TF-IDF is pure scikit-learn; the
embedding model is a free, locally-run Hugging Face checkpoint; BKT and the heuristic rankers are
plain Python; persistence is SQLite via SQLAlchemy; experiment tracking uses a local MLflow file
store. No paid APIs, API keys, or provisioned cloud resources anywhere in the codebase. CI
(`.github/workflows/ci.yml`) runs on GitHub's free Actions minutes -- checkout, install, `pytest`,
nothing more.

Job Radar keeps the same stance: every ATS adapter hits a public, unauthenticated endpoint;
`pypdf` is a free, pure-Python dependency; and PDF compilation uses a free local LaTeX
distribution (BasicTeX via Homebrew) rather than any hosted rendering service.

## Limitations

Opportunity Intelligence ranking specifically:

- Small (26-job), hand-curated, synthetic/sample demonstration dataset — not scraped or
  production data.
- Relevance labels are subjective ordinal judgments from one example candidate profile,
  not objective ground truth.
- No held-out user population, no online A/B test.
- The embedding model is general-purpose, not fine-tuned for job matching.
- TF-IDF is fit fresh per request over the current corpus, which is fine at this scale;
  production use would fit and version a vectorizer offline and transform requests
  against it.

Across the platform:

- No learned personalization anywhere — every ranker/score here (TF-IDF, embeddings, BKT, study
  ranking, Application Priority) is an unsupervised, deterministic, or configured-not-fit
  baseline. See Future Work.
- Single-user, no-auth by design (CLAUDE.md explicitly rules out multi-user/auth for now) — every
  endpoint reads the one checked-in example candidate profile; there is no concept of "whose"
  application/interview/mastery a row belongs to.
- BKT mastery has no forgetting/decay model — a skill practiced once six months ago and a skill
  practiced once yesterday are indistinguishable to the mastery cache itself (`study_ranking`'s
  `staleness` component is a ranking signal, not a mastery adjustment).
- Application status and interview results are entirely manually entered — nothing infers a
  status change or an interview outcome from any other signal.
- A `"pending"` interview result cannot be revised to `"passed"`/`"failed"` after the fact yet
  (Milestone 12); Application Priority has no persisted history, only a fresh computation per
  request (Milestone 13).
- `data/sample_jobs.csv`'s `application_deadline` values are static demo dates that will all
  eventually read as "passed" as real time moves past them.

Job Radar specifically:

- No skill extraction from a discovered job's free-text description yet — `to_job_record` sets
  `skills=[]`, so Role Fit still works (it scores free text too), but Readiness for a discovered
  job is currently a placeholder `1.0` ("nothing to be unprepared for"), and gaps/ATS coverage are
  trivially empty for those jobs. Honest, not fabricated, but a real gap.
- No soft-closure detection — a job that disappears from its source isn't marked `closed_at`.
- No HTTP retry/backoff or per-source circuit breaker on ingestion failures yet.
- No per-company notification cooldown or digesting of lower-confidence jobs.
- Resume tailoring has no API/dashboard wiring yet (CLI-only), no keyword substitution/wording
  variants (bullets render verbatim), no bold-emphasis reconstruction in rendered bullets, and
  bullets are reordered but never dropped for space — true page-length-constrained selection needs
  a compile-and-measure feedback loop.
- The Docker image does not install a LaTeX distribution, so resume PDF compilation is not
  available inside the container today (LaTeX source generation and the truth gate still are).

## Future work

Recorded here rather than half-built:

- A learned, interpretable preference model (e.g. logistic regression over semantic +
  structured features) compared against both content baselines.
- A hybrid ranker combining semantic similarity with structured features.
- Learning-to-rank once enough interaction data exists — the application-status and
  interview-outcome history from Milestones 11-12 is exactly the kind of interaction data this
  would eventually train against, once there's enough of it.
- A larger, legally sourced job dataset with held-out evaluation.
- A forgetting/decay model over BKT mastery (CLAUDE.md's future "Forgetting Modeling").
- Mistake classification over `CodingAttemptRecord.mistake_type` history (CLAUDE.md's future
  "Mistake Classification") — currently just structured, unaggregated data.
- Per-skill importance weighting for Readiness/Priority instead of uniform 1.0, once job postings
  carry a real weighting signal.
- Drift and service monitoring.
- Cloud deployment, only if a genuinely free and safe option is deliberately selected.
- Job Radar Checkpoint 6 (guarded subscription AI workbench), Checkpoint 7 (optional
  privacy-safe GitHub Actions discovery), and Checkpoint 8 (outcome analytics and hardening) —
  see `SWETrack_Job_Radar_Claude_Code_Handoff.md`.
