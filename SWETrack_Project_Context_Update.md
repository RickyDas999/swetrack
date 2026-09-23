# SWETrack Project Context Update

Use this file as project-level context alongside `SWETrack_Job_Radar_Claude_Code_Handoff.md`. This document explains the existing product, current known state, operating rules, and how Job Radar changes the roadmap.

## 1. Project identity

**Product:** SWETrack — SWE Recruiting and Interview Preparation Platform

**Earlier name:** RoleRank

**Primary user:** Subham Das, University of Wisconsin–Madison Computer Sciences student graduating May 2026 and pursuing U.S. new-grad software engineering roles.

**Candidate positioning:** Full-stack/backend software engineer who uses ML for purposeful product features—not an ML engineer first.

SWETrack is intended to centralize the user's new-grad recruiting workflow:

```text
Job discovery
→ role matching
→ application prioritization
→ resume tailoring
→ application tracking
→ skill-gap identification
→ LeetCode/System Design preparation
→ interview performance
→ updated readiness model
```

Job Radar is a module within SWETrack, not a separate product.

## 2. Current known implementation state

**Updated after Job Radar Checkpoints 0–5 (verified against the repository
and a live `pytest` run; see `docs/job-radar-integration-plan.md` for the
full Checkpoint 0 audit).** Everything from the original SWETrack
milestones plus all of Job Radar's MVP (Checkpoints 0–5) is implemented:

- Python 3.11 modular monolith; FastAPI backend; SQLAlchemy with local SQLite (no React — a single static, dependency-free HTML dashboard).
- TF-IDF role ranker and a Sentence Transformer (`all-MiniLM-L6-v2`) ranker, lazily loaded, both used for Role Fit.
- Precision@K / NDCG@K evaluation and local MLflow experiment tracking.
- Canonical skill taxonomy, deterministic alias normalization, immutable skill events, coding/System Design attempt tracking, Bayesian Knowledge Tracing mastery, explainable study recommendations.
- Separate Role Fit, Readiness, and Application Priority outputs (never conflated).
- Application pipeline and interview tracking, feeding decided outcomes back into mastery.
- **Job Radar (Checkpoints 0–5, all complete):** Greenhouse/Lever/Ashby/manual ingestion adapters; a validated source registry; persisted, deduplicated `discovered_jobs` (idempotent upsert, cross-source duplicate detection); a deterministic new-grad eligibility classifier with a 30-example labeled evaluation set; freshness decay scoring; discovered jobs feeding the existing Role Fit/Readiness/Priority pipeline unchanged; a job inbox API + dashboard panel distinguishing published-vs-first-found time; deduplicated macOS notifications with quiet hours and a priority threshold; a LaunchAgent for periodic sync; a resume evidence library parsed from a real resume with a truth gate, deterministic tailoring, and real one-page PDF generation (LaTeX/pdflatex).
- 304 passing tests as of this update.

This is context, not permission to assume the repository still matches it — the repository and current tests remain authoritative. Anything past this update (Checkpoint 6 onward) should be reverified the same way, not assumed from this bullet list.

## 3. Important model interpretation

The existing Role Fit system is content-based retrieval, not a supervised hiring-prediction model.

- TF-IDF and MiniLM produce similarity/relevance scores.
- Precision@K and NDCG@K evaluate ordering against a labeled dataset.
- Earlier results showed both rankers reaching P@5/NDCG@5 of 1.0 on a small 26-job curated set; this is not evidence that embeddings universally outperform TF-IDF or that the product predicts hiring.
- There is no confirmed mature user-feedback training loop yet.
- Role Fit must remain separate from readiness and application priority.

The three user-facing concepts are:

| Output | Meaning | Inputs |
|---|---|---|
| Role Fit | How closely a job matches the candidate's verified experience and target role | JD, profile, skills, TF-IDF, embeddings |
| Readiness | How prepared the candidate is for the role's skills/interviews | Practice history, skill events, mastery |
| Application Priority | Whether the role should be acted on now | Eligibility, freshness, fit, preferences, evidence coverage |

Do not merge these into one unexplained score.

## 4. New Job Radar scope

Job Radar adds four connected capabilities:

1. **Discovery:** Poll documented public ATS endpoints and accept manual job imports.
2. **Triage:** Normalize, deduplicate, classify eligibility, track freshness, and rank applications.
3. **Tailoring:** Build evidence-backed one-page LaTeX resumes and transparent ATS coverage/gap reports.
4. **Tracking:** Record job review, resume version, application status, interviews, and outcomes.

The full technical specification and implementation sequence are in `SWETrack_Job_Radar_Claude_Code_Handoff.md`.

### Job Radar MVP

Job Radar Checkpoints 0–5 define the MVP:

- Repository audit and integration plan.
- Greenhouse, Lever, and Ashby ingestion.
- Persistence, revisions, first-seen tracking, and deduplication.
- New-grad eligibility, freshness, Role Fit reuse, and explainable priority.
- Job inbox and local macOS notifications.
- Evidence library, one-page tailored resume, ATS coverage, gap report, and application tracking.

Later work:

- Checkpoint 6: guarded subscription AI workbench.
- Checkpoint 7: optional privacy-safe GitHub Actions discovery.
- Checkpoint 8: outcome analytics and hardening.

Do not delay the MVP for the later checkpoints.

## 5. Candidate and search context

Seed these as editable profile defaults, not hard-coded logic:

- Graduation: May 2026.
- Degree: B.S. Computer Sciences, University of Wisconsin–Madison.
- Minors: General Business and Entrepreneurship.
- U.S. citizen/permanent U.S. work authorization; does not require sponsorship.
- Primary target: new-grad Software Engineer, Backend Engineer, Full-Stack Engineer, Product Software Engineer, Cloud Engineer, and Platform Engineer.
- Secondary target: AI Software Engineer or ML Platform Engineer when the work is still software-engineering centered.
- Preferred locations include New York City, New Jersey, and Chicago.
- Other U.S. locations and U.S.-remote roles are acceptable.
- Exclude senior, staff, principal, lead, manager, architect, and director roles unless the title is clearly mislabeled and requirements indicate entry level.

The user wants to apply quickly, but speed must not weaken truthfulness or application quality.

## 6. Resume evidence context

The resume is one-page LaTeX. Tailoring should maintain one truthful master resume and select/reorder approved evidence for each job.

### AWS TrackPoint

Relevant verified themes to preserve according to the current master resume:

- AWS Software Development Engineer internship.
- Serverless workflow-tracking service using Java, AWS Lambda, API Gateway, and DynamoDB.
- Versioned current-state and immutable task history.
- DynamoDB Streams and Lambda audit pipeline.
- Querying across 100+ task attributes.
- Approximately 500K+ annual workflows where supported by the current resume.
- Reduced stakeholder reporting effort by 80% and saved 100+ engineering/program-management hours per week where supported by the current resume.
- Production delivery using internal build/deployment tooling, CDK-managed infrastructure, staged deployments, integration tests, and CloudWatch monitoring/alarms where supported by repository/resume evidence.

### Johnson & Johnson

- Software Asset Management internship.
- Python, Power BI, SQL, Excel, Selenium/BeautifulSoup, data catalog automation, and Scrum.
- Data Knowledge Core generative-AI chatbot work.
- Global software-purchase visibility covering $100M+ where supported by the current resume.
- Verified $18,399 cost avoidance over three months.
- Larger modeled savings/time estimates may be used only if retained and approved in the current master resume.

### Capital One Capstone

- Full-stack fraud-detection service.
- Random Forest evaluated on 1M+ simulated transactions.
- 99.3%+ measured accuracy.
- AWS-backed transaction processing and user configuration.
- Configurable Twilio SMS alerts, or the currently implemented/approved alerting technology.

### SWETrack

Only claim features that exist in the audited repository. Likely supported themes include:

- FastAPI, SQLAlchemy/SQLite, Docker, and pytest.
- TF-IDF and Sentence Transformer semantic role ranking.
- Precision@K, NDCG@K, and local MLflow evaluation.
- Skill taxonomy, immutable events, BKT mastery, coding/System Design tracking, readiness, and explainable recommendations if confirmed.
- Job Radar features become resume-eligible only after they are implemented and verified.

### Resume truth policy

- Every tailored claim must map to a stable evidence ID.
- Never add a skill solely because it appears in the job description.
- Never alter dates, titles, employers, metrics, scale, or deployment status without approved evidence.
- Missing job requirements belong in a gap report, not in the resume.
- Planned features must never be written as completed work.
- Every output must remain one page and ATS-parseable.

## 7. Cost and technology constraints

Hard constraint: **$0 additional cost**.

- No paid LLM APIs.
- No required cloud database or paid hosted service.
- No scraping proxy, CAPTCHA service, or paid job-data provider.
- Prefer local and open-source tooling.
- ChatGPT Plus is an interactive review surface, not an API backend.
- Claude Pro/Claude Code may be used within subscription limits for development and explicit, user-triggered assistance.
- Continuous job discovery must not require LLM calls.
- The deterministic app must remain useful if Claude or ChatGPT is unavailable.
- Optional GitHub Actions discovery may be added later with personal data excluded and cost safeguards enabled.

Avoid unnecessary infrastructure such as Kubernetes, Redis, Kafka, Celery, or a vector database unless a measured requirement emerges later.

## 8. Data-source and automation boundaries

Preferred sources:

- Greenhouse public Job Board API.
- Lever public Postings API.
- Ashby public Job Postings API.
- Explicit public RSS/JSON feeds.
- Reviewed and permitted public career pages.
- Manual URL or pasted-JD import for unsupported systems such as Workday.

Forbidden or out of scope:

- Scraping authenticated LinkedIn, Indeed, or Handshake pages.
- Bypassing anti-bot systems, rate limits, or CAPTCHAs.
- Storing browser cookies or subscription session credentials.
- Automatically answering legal, demographic, disability, work-authorization, or sponsorship questions.
- Automatically submitting job applications.

The app prepares and prioritizes; the user reviews and submits.

## 9. Claude Code operating procedure

Claude Code is the implementation environment. The user reviews and commits changes manually.

For every checkpoint Claude Code must:

1. Read the project context and relevant handoff section.
2. Inspect current code before proposing changes.
3. State the exact checkpoint scope and acceptance criteria.
4. Modify only what belongs to that checkpoint.
5. Add or update automated tests.
6. Run relevant tests and show results.
7. Report changed files and important decisions.
8. Identify any incomplete or unverified item honestly.
9. Suggest one conventional commit message.
10. Stop and wait for the user to review and commit.

Claude Code must never:

- commit or push;
- combine several milestones into a giant rewrite;
- silently introduce paid services;
- provision cloud infrastructure;
- overwrite working architecture without evidence;
- describe failing or untested work as complete;
- modify the resume to claim a newly planned feature before it is finished.

The user will bring milestone results back to ChatGPT for validation, interview-level explanation, architecture review, and the next handoff.

## 10. How the ChatGPT Project should respond

When helping with SWETrack:

- Treat the repository, test output, and current documents as authoritative.
- Ask for or inspect Claude Code's milestone summary before asserting implementation status.
- Clearly label information as **implemented**, **verified**, **planned**, or **proposed**.
- Protect the distinction between Role Fit, Readiness, and Application Priority.
- Optimize first for a useful, resume-ready vertical slice.
- Prefer explainable baselines and measured evaluation over unnecessary model complexity.
- Teach the user what was built at a software-engineering interview level after each checkpoint.
- Review metrics critically; small curated evaluations are not evidence of broad generalization.
- Keep resume language concise, non-redundant, truthful, and aligned with full-stack/backend SWE positioning.
- Maintain the no-cost boundary.

## 11. Immediate next action

**Superseded.** Job Radar Checkpoints 0–5 (the full MVP: repository audit,
ingestion, persistence/dedup, eligibility/priority, inbox/notifications,
and resume tailoring) are complete — see `docs/job-radar-integration-plan.md`
for the Checkpoint 0 audit this section originally asked for, and the
repository/git history for everything built since.

The next actual next action is **Job Radar Checkpoint 6 — subscription AI
workbench** (`SWETrack_Job_Radar_Claude_Code_Handoff.md` Section 18), unless
the user directs otherwise. As always, audit the real repository state
before starting rather than assuming this file is current.

## 12. Files to keep together

Add both of these files to the SWETrack ChatGPT Project and the repository root during the audit:

1. `SWETrack_Project_Context_Update.md` — product memory, constraints, current known state, and collaboration rules.
2. `SWETrack_Job_Radar_Claude_Code_Handoff.md` — detailed architecture, schemas, testing requirements, checkpoints, and initial Claude Code prompt.

If these documents conflict with the audited repository, record the discrepancy in the Checkpoint 0 integration plan rather than silently changing either implementation or history.
