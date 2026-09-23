# AGENTS.md — RoleRank → SWETrack Migration

## Current Status (read this first)

**The migration this document describes is complete.** RoleRank → SWETrack
(Phases 0–14 below, delivered as this repo's own Milestones 1–15) shipped
long ago. Job Radar (a further extension covering job discovery/ingestion,
eligibility, priority, an inbox, notifications, and resume tailoring —
`SWETrack_Job_Radar_Claude_Code_Handoff.md`) has also completed Checkpoints
0–5 of its own plan.

Everything below this point — including "PHASE 0 — DISCOVERY BEFORE
CHANGING CODE" and "FIRST ACTION" — is the **original migration plan**,
kept for its still-relevant standing philosophy (cost constraints,
incremental-milestone workflow, "do not overbuild," interview-readiness
framing, the canonical skill taxonomy design, etc.), not as a next step.
**Do not treat "FIRST ACTION" as the next action.** For the actual current
state of the repository, read:

- `README.md` — verified, current architecture and every shipped feature
- `docs/job-radar-integration-plan.md` — Job Radar's audited integration
  plan and decision record (Checkpoint 0), with the checkpoints since built
  on top of it
- `git log` — the real, current commit history

The **incremental-milestone workflow, cost constraints, "do not overbuild,"
and never-commit-without-asking rules below still apply to all future
work** (including Job Radar Checkpoints 6+ and anything beyond it) — only
the specific Phase/Milestone checklist is historical.

## Project Context

This repository currently contains **RoleRank**, an ML-powered job matching and ranking system for new-grad SWE recruiting.

The project is now expanding into **SWETrack**, a broader personalized recruiting and interview intelligence platform.

SWETrack should centralize the user's daily new-grad SWE workflow across:

* job discovery
* role matching
* opportunity ranking
* application tracking
* interview tracking
* LeetCode preparation
* System Design preparation
* software-engineering skill mastery
* readiness estimation
* personalized study recommendations

The existing RoleRank functionality is **not being discarded**.

Instead:

> RoleRank becomes the Opportunity Intelligence subsystem inside SWETrack.

The migration must preserve existing working functionality wherever possible.

---

# Primary Product Definition

SWETrack is:

> A personalized ML platform that connects software-engineering job opportunities with the user's evolving technical skills, interview readiness, and study priorities.

The long-term product loop is:

```text
Job Discovery
    ↓
Role Matching
    ↓
Skill Requirements
    ↓
Current Skill Mastery
    ↓
Readiness Gaps
    ↓
Recommended Preparation
    ↓
Coding / System Design Practice
    ↓
Interview Performance
    ↓
Updated Skill Model
    ↓
Better Role + Study Prioritization
```

---

# Important Development Workflow

This project must continue using the same incremental development style as before.

## Do NOT implement the full migration in one giant change.

Work milestone by milestone.

For each milestone:

1. Inspect the current repository.
2. Understand the existing implementation before changing it.
3. Propose the smallest coherent set of changes.
4. Implement that milestone only.
5. Run relevant tests.
6. Run lint/type checks if configured.
7. Report exactly what changed.
8. Suggest an appropriate commit message.
9. STOP.

The user will manually review/test the work.

The user will create and push the Git commit.

## Never automatically push code.

Do not:

* run `git push`
* rewrite Git history
* force push
* create remote branches without being asked
* combine multiple major milestones into one commit

You may inspect Git status/history when useful.

---

# Existing RoleRank Philosophy

Preserve the project qualities already established during RoleRank development:

* production-shaped architecture
* meaningful ML rather than API wrappers
* explicit baselines
* reproducible evaluation
* typed interfaces
* strong tests
* clear separation between API, ML, and business logic
* explainable ranking
* Dockerized runtime
* free/local development
* no unnecessary paid services
* honest metrics
* no fabricated claims

The goal is to produce a strong new-grad SWE / ML engineering portfolio project.

---

# Cost Constraint

SWETrack must remain **$0 to run for development**.

Prefer:

* local development
* open-source libraries
* locally runnable ML models
* free GitHub Actions usage
* PostgreSQL in Docker
* deterministic seed data

Avoid:

* paid APIs
* required AWS/GCP/Azure resources
* SaaS dependencies that incur charges
* paid vector databases
* paid LLM APIs

Optional external integrations may be added later only if a fully free/local path remains available.

---

# PHASE 0 — DISCOVERY BEFORE CHANGING CODE

Before modifying anything:

## Inspect the repository

Determine:

* current directory structure
* package/module names
* existing FastAPI app layout
* existing ranking pipeline
* embedding/model loading implementation
* existing job schemas
* existing candidate/resume schemas
* current storage approach
* existing tests
* current Docker configuration
* current CI
* current docs
* current environment variable names
* references to "RoleRank"
* references to repo/package names
* existing evaluation scripts
* MLflow usage if still present

Do not assume the codebase exactly matches older plans.

The repository is the source of truth.

---

# PHASE 1 — PRODUCT / REPOSITORY RENAME

## Goal

Migrate user-facing and repository-facing naming from:

```text
RoleRank
```

to:

```text
SWETrack
```

without breaking existing functionality.

---

## Rename Scope

Search the repository for:

```text
RoleRank
rolerank
ROLE_RANK
role-rank
role_rank
```

Determine which references are:

### Product-facing

These should generally become SWETrack.

Examples:

* README title
* API title
* Docker service name if appropriate
* docs
* comments describing the product
* package metadata
* app metadata
* sample commands
* environment examples

### Internal Opportunity-Ranking Concepts

These should NOT necessarily disappear.

The original RoleRank matching/ranking engine is now conceptually:

```text
SWETrack Opportunity Intelligence
```

or internally:

```text
opportunities
```

Avoid renaming useful ML terms just for branding.

Example:

```python
rank_roles(...)
```

can remain conceptually valid.

But:

```python
RoleRankApplication
```

should likely become something SWETrack-specific if it represents the whole application.

---

## Package Naming

If the repository currently has a package named:

```text
rolerank
```

evaluate the blast radius before changing it.

Preferred final package:

```text
swetrack
```

BUT do not perform a package rename blindly if it creates an unnecessarily risky first commit.

If the migration is significant:

### Commit A

Product branding/documentation rename.

### Commit B

Python package/module rename.

This keeps changes reviewable.

---

# PHASE 2 — MODULAR DOMAIN REORGANIZATION

## Goal

Evolve the architecture toward a modular monolith.

SWETrack should eventually contain these core domains:

```text
SWETrack
│
├── Opportunities
├── Skills
├── Learning
└── Interviews
```

The existing RoleRank implementation should become the **Opportunities** domain.

Do not rewrite stable working code purely to fit a prettier folder tree.

Refactor incrementally.

Preferred eventual structure:

```text
src/swetrack/
│
├── api/
│
├── core/
│
├── domains/
│   │
│   ├── opportunities/
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── services.py
│   │   ├── repositories.py
│   │   └── ranking/
│   │
│   ├── skills/
│   │   ├── models.py
│   │   ├── taxonomy.py
│   │   └── services.py
│   │
│   ├── learning/
│   │   ├── attempts/
│   │   ├── mastery/
│   │   ├── recommendations/
│   │   └── services.py
│   │
│   └── interviews/
│       ├── models.py
│       ├── schemas.py
│       └── services.py
│
├── ml/
│   ├── embeddings/
│   ├── knowledge_tracing/
│   ├── ranking/
│   └── evaluation/
│
└── infrastructure/
    ├── database/
    ├── config/
    └── logging/
```

This is a target architecture, not permission to perform a massive refactor immediately.

---

# PHASE 3 — PRESERVE ROLERANK AS OPPORTUNITY INTELLIGENCE

The current RoleRank feature set should remain functional.

At minimum preserve:

* candidate/resume representation
* job representation
* job ingestion path
* skill/preference matching
* embeddings
* semantic similarity
* ranking
* ranking explanations
* FastAPI serving
* model loading
* unit/integration tests
* Docker runtime
* evaluation tooling

Do not regress working RoleRank functionality during SWETrack migration.

---

# Opportunity Intelligence Responsibilities

The Opportunity module will eventually own:

```text
Job / Role
Company
Location
Description
Skills
Requirements
Preferences
Fit Score
Ranking Explanation
Application Status
Interview Pipeline
```

The current RoleRank score becomes:

```text
Role Fit Score
```

This terminology matters because SWETrack will introduce separate concepts later:

```text
Role Fit
Interview Readiness
Application Priority
```

Do not combine these into one opaque score.

---

# PHASE 4 — CANONICAL SKILL MODEL

This is the most important architectural addition.

SWETrack needs one canonical representation of software-engineering skills shared across:

* resumes
* job descriptions
* LeetCode
* System Design
* interviews
* learning activities

---

## Example taxonomy

```text
Software Engineering
│
├── Programming Languages
│   ├── Python
│   ├── Java
│   └── JavaScript
│
├── Algorithms
│   ├── Dynamic Programming
│   ├── Graphs
│   ├── Trees
│   └── Binary Search
│
├── Data Structures
│   ├── Hash Maps
│   ├── Heaps
│   ├── Queues
│   └── Tries
│
├── Backend
│   ├── REST APIs
│   ├── Authentication
│   └── Async Processing
│
├── Data Systems
│   ├── SQL
│   ├── NoSQL
│   ├── Indexing
│   └── Data Modeling
│
├── Distributed Systems
│   ├── Caching
│   ├── Partitioning
│   ├── Replication
│   ├── Messaging
│   └── Consistency
│
└── Reliability
    ├── Retries
    ├── Idempotency
    ├── Failover
    └── Observability
```

---

## Requirements

A skill should eventually support fields similar to:

```python
id
slug
name
category
parent_id
```

Potential future metadata:

```python
aliases
description
importance
```

Avoid overengineering now.

---

## Skill normalization

The same concept should map to one canonical skill.

Examples:

```text
"DynamoDB"
"Amazon DynamoDB"
"AWS DynamoDB"
```

→ one canonical skill.

```text
"Dynamic Programming"
"DP"
```

→ one canonical skill.

Skill normalization may initially use deterministic alias mapping.

Do not use embeddings merely because they are available if deterministic normalization is sufficient.

---

# PHASE 5 — MAP EXISTING ROLERANK DATA TO SKILLS

The existing RoleRank pipeline likely has:

* extracted resume skills
* job skills
* preference signals
* semantic features

Do not discard them.

Map existing structured skill features to the canonical skill taxonomy.

The opportunity ranking pipeline should continue to work while progressively consuming canonical skills.

---

# PHASE 6 — LEARNING DOMAIN

Once the migration and shared skill model are stable, add SWETrack's learning engine.

This domain tracks:

* Coding practice
* System Design practice
* Skill observations
* Skill mastery
* Study recommendations

---

# Learning Event Model

Do not store only a mutable score such as:

```text
dynamic_programming = 0.64
```

Preserve immutable learning observations.

Conceptually:

```python
SkillEvent(
    id,
    skill_id,
    source_type,
    source_id,
    timestamp,
    outcome,
    evidence_weight,
)
```

Possible source types:

```text
coding_attempt
system_design_attempt
interview_feedback
concept_review
```

Historical evidence should remain replayable so future models can recompute mastery.

---

# PHASE 7 — CODING PREPARATION

Add support for coding interview practice.

An attempt should eventually contain:

```text
problem
difficulty
skills
success
duration
hints_used
confidence
mistake_type
timestamp
```

Example mistake categories:

```text
algorithm_selection
state_definition
recurrence
off_by_one
pointer_management
base_case
complexity
data_structure_choice
mutation
edge_case
```

Do not implement automatic code analysis initially unless specifically requested.

Manual structured data is acceptable and often better quality.

---

# PHASE 8 — SYSTEM DESIGN PREPARATION

Add structured System Design evaluations.

Core skill dimensions:

```text
requirements
capacity_estimation
api_design
data_modeling
database_selection
indexing
caching
load_balancing
partitioning
replication
messaging
consistency
reliability
idempotency
observability
bottleneck_analysis
tradeoff_reasoning
communication
```

One design session should update multiple skills.

Example:

```json
{
  "problem": "Design Ticketmaster",
  "scores": {
    "requirements": 0.9,
    "capacity_estimation": 0.6,
    "consistency": 0.5,
    "reliability": 0.4,
    "tradeoff_reasoning": 0.7
  }
}
```

Manual rubric entry should be the initial baseline.

Do not make a paid LLM evaluator a dependency.

---

# PHASE 9 — BAYESIAN KNOWLEDGE TRACING

Use Bayesian Knowledge Tracing as the first mastery model.

For each skill model:

```text
P(L0) = initial mastery
P(T)  = probability of learning
P(G)  = guess probability
P(S)  = slip probability
```

The implementation should live outside business/database logic.

Preferred location:

```text
ml/knowledge_tracing/bkt.py
```

BKT must be:

* configurable
* unit tested
* deterministic
* numerically safe

Do not pretend initial BKT parameter values were learned if they are configured defaults.

---

# PHASE 10 — EXPLAINABLE STUDY RANKING

Study recommendations should initially use a deterministic explainable ranker.

Potential components:

```text
mastery gap
difficulty fit
practice staleness
skill importance
recent repetition penalty
job demand
interview demand
```

A recommendation should include component-level explanations.

Example:

```json
{
  "activity": "Design Distributed Rate Limiter",
  "score": 0.84,
  "components": {
    "mastery_gap": 0.78,
    "job_demand": 0.88,
    "staleness": 0.65,
    "difficulty_fit": 0.81,
    "repetition_penalty": 0.06
  }
}
```

Do not describe this first study ranker as machine-learned.

It is an explainable heuristic ranker consuming ML-derived mastery signals.

---

# PHASE 11 — CONNECT OPPORTUNITIES TO LEARNING

This is the core SWETrack integration.

Each opportunity should eventually have structured skill requirements.

Example:

```json
{
  "java": 0.8,
  "distributed_systems": 0.7,
  "sql": 0.5,
  "graphs": 0.4
}
```

The learner profile contains estimated mastery:

```json
{
  "java": 0.65,
  "distributed_systems": 0.49,
  "sql": 0.81,
  "graphs": 0.61
}
```

SWETrack computes gaps.

---

# Job-specific Readiness

Add a concept distinct from Role Fit:

```text
ROLE FIT
How well does this opportunity align with the candidate?
```

versus:

```text
READINESS
How prepared is the user for the skills associated with this opportunity?
```

Never conflate them.

Example:

```text
Role Fit:   91%
Readiness:  67%
```

---

# Future API

Eventually support something like:

```text
GET /opportunities/{id}/readiness
```

Response:

```json
{
  "fit_score": 0.91,
  "readiness_score": 0.67,
  "skill_gaps": [
    {
      "skill": "distributed_systems",
      "required": 0.8,
      "mastery": 0.49,
      "gap": 0.31
    }
  ],
  "recommended_activities": []
}
```

This should become one of the project's flagship workflows.

---

# PHASE 12 — APPLICATION / RECRUITING PIPELINE

Eventually add application lifecycle tracking.

Possible statuses:

```text
discovered
interested
applied
oa
recruiter_screen
technical
system_design
behavioral
final
offer
rejected
withdrawn
```

Store timestamps where useful.

Avoid premature ML on application outcomes until enough real data exists.

---

# PHASE 13 — INTERVIEW DOMAIN

Track interview events such as:

```text
company
role
round_type
date
skills_tested
result
notes
feedback
```

Potential round types:

```text
recruiter
oa
coding
system_design
behavioral
hiring_manager
final
```

Interview performance can later emit SkillEvents and update mastery.

Do not infer mastery automatically from vague notes in the first implementation.

Structured user-entered feedback should remain the baseline.

---

# PHASE 14 — APPLICATION PRIORITY

Eventually derive:

```text
Application Priority
```

from separate signals.

Possible components:

```text
role fit
readiness
user preference
deadline urgency
company interest
location
compensation
```

Keep each component visible.

Do not create one mysterious ML-generated number.

---

# ML RESPONSIBILITIES

SWETrack will eventually contain several ML systems.

They must remain conceptually distinct.

## Existing / RoleRank

### Semantic Job Matching

Embeddings / similarity.

Purpose:

```text
candidate ↔ opportunity relevance
```

### Opportunity Ranking

Structured and semantic features.

Purpose:

```text
which jobs best fit the user?
```

---

## New / SWETrack

### Knowledge Tracing

Purpose:

```text
what skills does the user likely understand?
```

### Performance Prediction

Purpose:

```text
how likely is success on an activity requiring skill X?
```

### Study Ranking

Purpose:

```text
what should the user study next?
```

### Forgetting Modeling

Future.

Purpose:

```text
which knowledge is likely decaying?
```

### Mistake Classification

Future.

Purpose:

```text
why are coding attempts failing?
```

Do not mix these objectives into one model.

---

# Evaluation Philosophy

Every ML component should have an explicit baseline.

Examples:

## Role ranking

Compare against simple lexical/structured baselines where relevant.

## Knowledge tracing

Compare against:

```text
historical success rate per skill
```

Metrics:

```text
Brier score
log loss
calibration
```

Use chronological evaluation.

Do not randomly split sequential learner data.

## Mistake classification

Later use:

```text
macro F1
precision
recall
confusion matrix
```

## Recommendation

Initially offline heuristic validation.

Later consider:

```text
NDCG
MRR
learning-gain outcomes
```

Never fabricate superiority.

---

# Data Integrity

Distinguish clearly between:

* real user data
* curated activity metadata
* synthetic demonstration events

Never describe synthetic history as real usage.

Seed generators should be deterministic.

---

# Privacy

SWETrack may contain:

* resumes
* job applications
* interview notes
* coding performance
* personal preferences

Avoid unnecessarily logging raw sensitive data.

Do not log full resume text or source code by default.

Keep local-first architecture.

---

# API Philosophy

Prefer resource-oriented routes.

Potential future organization:

```text
/opportunities
/applications
/interviews
/skills
/learning
/mastery
/recommendations
/readiness
```

Do not implement all endpoints simply because they appear here.

Only add routes as each milestone requires them.

---

# Testing Expectations

Each incremental commit should add or preserve tests.

Tests should cover behavior, not merely line execution.

Categories should eventually include:

```text
unit
integration
API
ML evaluation
```

Critical flows:

* existing RoleRank ranking behavior remains stable
* skill normalization
* learning-event persistence
* BKT updates
* System Design multi-skill updates
* study ranking
* role-specific readiness
* transaction atomicity

---

# Documentation Migration

Update documentation progressively.

The README should eventually present SWETrack, not RoleRank.

Recommended top-level framing:

```text
SWETrack
Personalized Recruiting & Interview Intelligence for Software Engineers
```

Explain four main product areas:

```text
Opportunity Intelligence
Interview Tracking
Skill Intelligence
Adaptive Preparation
```

README architecture should show the closed loop:

```text
Jobs
  ↓
Role Ranking
  ↓
Skill Requirements
  ↓
Readiness Gap
  ↓
Study Recommendations
  ↓
Practice
  ↓
Interview
  ↓
Skill Updates
```

---

# Resume-Safe Project Description

The eventual project description should be roughly:

> SWETrack is a personalized ML platform for new-grad SWE recruiting and interview preparation that combines semantic opportunity ranking with probabilistic skill modeling and adaptive study recommendations.

Never update README/resume claims ahead of implementation.

---

# Current Resume Target

After the relevant features actually exist, the project should support bullets similar to:

* Built a personalized ML platform centralizing new-grad SWE recruiting and interview preparation, combining semantic job-role ranking with skill modeling across coding and System Design.

* Developed a shared software-engineering skill graph connecting resume experience, job requirements, coding attempts, and design evaluations to generate role-specific readiness gaps.

* Implemented Bayesian Knowledge Tracing over sequential practice events and an explainable recommendation engine prioritizing preparation using mastery, role demand, difficulty, and practice recency.

* Served opportunity ranking, readiness, and learning workflows through a tested FastAPI service with reproducible ML evaluation, Dockerized runtime, and CI.

Only include claims corresponding to completed functionality.

---

# Initial Migration Milestones

Follow these in order unless repository inspection reveals a safer sequencing.

## M0 — Repository Audit

Deliver:

* current architecture summary
* RoleRank references
* likely migration blast radius
* proposed first commit

Do not change code yet unless the changes are trivial and clearly safe.

STOP after reporting.

---

## M1 — Product Rename

Goal:

```text
RoleRank → SWETrack
```

Scope primarily:

* README
* app title
* project metadata
* docs
* Docker naming where safe
* examples
* user-facing text

Preserve existing opportunity-ranking behavior.

Run all existing tests.

STOP.

Suggested commit:

```text
refactor: rename RoleRank product to SWETrack
```

---

## M2 — Package Rename If Necessary

Only if package/module is still `rolerank` and migration is justified.

Rename carefully:

```text
rolerank → swetrack
```

Update:

* imports
* test imports
* commands
* Docker
* CI
* packaging
* module execution paths

Do not combine this with new functionality.

Run the complete test suite.

STOP.

Suggested commit:

```text
refactor: migrate Python package to swetrack
```

---

## M3 — Opportunity Domain Boundary

Encapsulate existing RoleRank functionality under an Opportunities-oriented module/domain.

No behavioral changes unless necessary.

Do not rewrite working algorithms.

STOP.

Possible commit:

```text
refactor: organize role ranking under opportunities domain
```

---

## M4 — Canonical Skill Taxonomy

Introduce:

* Skill representation
* categories
* aliases
* normalization
* initial taxonomy

Integrate existing RoleRank structured skill matching gradually.

Preserve ranking outputs where practical.

STOP.

Possible commit:

```text
feat: add canonical software engineering skill taxonomy
```

---

## M5 — Learning Event Foundation

Introduce:

* learning activities
* attempts
* skill events
* immutable history
* persistence

No BKT yet unless the milestone remains small enough.

STOP.

Possible commit:

```text
feat: add learning event model for interview preparation
```

---

## M6 — Bayesian Knowledge Tracing

Implement:

* BKT model
* configurable parameters
* mastery persistence
* sequential updates
* tests
* baseline evaluation scaffold

STOP.

Possible commit:

```text
feat: add Bayesian knowledge tracing for skill mastery
```

---

## M7 — Coding Practice

Support structured LeetCode/coding attempts.

Connect to SkillEvents/BKT.

STOP.

Possible commit:

```text
feat: track coding practice and mastery updates
```

---

## M8 — System Design Practice

Support:

* System Design activity
* rubric
* multiple skill observations
* atomic mastery updates

STOP.

Possible commit:

```text
feat: track system design practice across skill rubric
```

---

## M9 — Adaptive Study Recommendations

Build explainable heuristic ranking using:

* mastery gap
* recency
* difficulty
* repetition
* priority

STOP.

Possible commit:

```text
feat: rank personalized study activities
```

---

## M10 — Role Readiness Integration

Connect:

```text
Opportunity requirements
        +
Skill mastery
        ↓
Role readiness
```

Expose skill gaps and suggested preparation.

This is a major project milestone.

STOP.

Possible commit:

```text
feat: generate role-specific readiness and skill gaps
```

---

# Codex Behavior After Every Milestone

At the end of each milestone return:

## Summary

What was implemented.

## Files Changed

List important files.

## Design Decisions

Explain non-obvious architecture choices.

## Verification

Commands run and exact result summaries.

Example:

```text
pytest: 47 passed
ruff: passed
```

Do not invent numbers.

## Manual Testing

Give the user specific steps to test locally.

## Known Limitations

Anything intentionally deferred.

## Proposed Commit

Provide exactly one clean commit message.

## Next Milestone

Describe the next milestone briefly.

Then STOP.

Wait for the user to review and push the commit.

---

# Debugging Workflow

The user will handle most iterative debugging inside Codex.

When something fails:

1. inspect the actual error
2. identify root cause
3. fix the smallest responsible area
4. rerun targeted tests
5. rerun broader verification if shared code changed

Do not redesign the architecture merely because one test fails.

---

# IMPORTANT — DO NOT OVERBUILD

Avoid adding these during the initial migration:

* microservices
* Kafka
* Kubernetes
* Redis without a demonstrated need
* vector databases without a demonstrated need
* paid LLM integrations
* graph neural networks
* deep knowledge tracing
* reinforcement learning
* browser extensions
* VS Code extension
* complex frontend redesign
* authentication
* multi-user SaaS infrastructure

The priority is:

```text
correct core architecture
→ real ML
→ evaluation
→ tests
→ integration
→ product polish
```

---

# Interview-Level Engineering Principles

The implementation should be defensible in an interview.

Be prepared to explain through the code:

## Why a modular monolith?

Because the domains are closely related, deployment complexity is unnecessary, and clear internal boundaries provide most of the benefits required at current scale.

## Why immutable SkillEvents?

They preserve source observations and allow mastery state to be recomputed when models change.

## Why separate Role Fit and Readiness?

Fit represents candidate-role alignment; readiness represents the user's estimated preparation for required skills. They answer different questions.

## Why BKT?

It provides an interpretable probabilistic baseline for latent skill mastery using sequential observations.

## Why not Deep Knowledge Tracing immediately?

Insufficient behavioral data and unnecessary model complexity. Establish a strong interpretable baseline first.

## Why heuristic study ranking first?

There is not yet sufficient outcome data to train a trustworthy learning-to-rank model.

## Why preserve RoleRank?

The existing semantic ranking system is a functioning and valuable subsystem. SWETrack expands its context rather than replacing it.

---

# Product End State

The target user experience is:

```text
SWETrack

Top Opportunities
────────────────────────────
Figma SWE
Fit: 93%
Readiness: 72%

TikTok Backend
Fit: 91%
Readiness: 64%

Capital One TDP
Fit: 88%
Readiness: 84%

Interview Readiness
────────────────────────────
Coding:         78%
System Design:  63%

Weakest Skills
────────────────────────────
Reliability             47%
Dynamic Programming     55%
Consistency             57%

Today's Preparation
────────────────────────────
1. Graph practice
2. Design Distributed Rate Limiter
3. Review replication/failover

Reason:
These concepts are weak and appear across
multiple high-priority active opportunities.
```

That is the product direction all future architecture should support.

---

# FIRST ACTION

Do not immediately refactor.

Start by inspecting the repository and return:

1. current repository tree
2. current architecture
3. existing RoleRank ML pipeline
4. all major references that need renaming
5. risks associated with package/repo rename
6. proposed scope for **M1: product rename**
7. exact files you would change
8. tests/commands you would run
9. proposed commit message

Then STOP.

Wait for the user to approve or request implementation of M1.
