# SWETrack UI Implementation Handoff

## Purpose

Continue from the verified shadcn dashboard foundation and turn it into a cohesive SWETrack product UI through small, reviewable checkpoints.

This document intentionally does not repeat the backend, ML, domain, or product context already available in `CLAUDE.md` and the existing project documentation. Inspect those sources and the repository when exact routes, schemas, or domain behavior are needed.

## Verified starting point

- React + TypeScript + Vite frontend exists under `frontend/`.
- shadcn/ui is initialized with the Radix base, Nova preset, and Tailwind CSS v4 through `@tailwindcss/vite`.
- The official `dashboard-01` block is installed.
- `src/pages/DashboardPage.tsx` is rendered through `src/App.tsx`.
- `src/main.tsx` wraps the application in `TooltipProvider` for the sidebar tooltips.

Do not reinstall or replace this foundation.

## Operating rules

1. Execute only the checkpoint explicitly authorized by the user. Do not begin the next checkpoint automatically.
2. Before editing, inspect the current repository state and `git diff` so existing work is preserved.
3. Never commit, push, amend, reset, or rewrite Git history. The user performs commits manually.
4. At each checkpoint, provide a suggested commit message and wait for user confirmation.
5. Preserve the FastAPI backend and `static/dashboard.html` until the React UI has verified feature parity. Do not remove the legacy dashboard without explicit authorization.
6. Do not modify backend contracts merely to make frontend implementation easier. If an endpoint or field is missing, document the gap and stop or use a clearly isolated frontend state—not fabricated server behavior.
7. Do not invent metrics, ML results, deadlines, jobs, skill mastery, application outcomes, or analytics values.
8. Use shadcn/ui as the single component system. Do not introduce MUI, Chakra, Ant Design, Bootstrap, Flowbite, or another overlapping component library.
9. Keep the project fully local and free to run. Do not introduce paid APIs, hosted services, telemetry, or SaaS dependencies.
10. Prefer reusable feature components over page-sized monoliths, but do not create abstractions without an immediate use.
11. Keep generated shadcn primitives under `src/components/ui/`; do not place product-specific business logic there.
12. Run the existing frontend build, lint, and tests after every checkpoint. Run relevant backend tests only if backend files were explicitly changed.

## Product design standard

The UI should resemble a serious internal productivity product, not a generic generated admin dashboard.

### Visual direction

- Calm, neutral, information-dense interface with one restrained accent color.
- Strong typography hierarchy and consistent spacing.
- Cards only when they express a meaningful group or summary; do not place every section in a floating card.
- Tables and lists should be optimized for scanning, filtering, and action.
- Use color to communicate state or priority, not decoration.
- Avoid gradients, glassmorphism, oversized statistic cards, excessive rounded pills, decorative AI sparkles, animated backgrounds, and marketing-page styling.
- Retain the Nova preset as the base, then define SWETrack-specific semantic tokens rather than scattering arbitrary Tailwind colors across components.
- Prefer a system font stack unless an existing local font setup is already present.

### Interaction standard

Every data-backed screen must eventually support four explicit states:

1. Loading
2. Empty
3. Error with a useful recovery action
4. Loaded

Interactive controls must have visible focus states, accessible labels, keyboard support, and disabled behavior where appropriate. Do not encode meaning through color alone.

### Domain clarity

- Keep Role Fit, Readiness, and Application Priority visually and semantically distinct.
- Show score components and explanations wherever the backend provides them; do not reduce explainable results to an unexplained percentage.
- Identify heuristic, deterministic, unsupervised, and learned behavior accurately in user-facing explanatory text.
- Never imply that an untrained or configured model learned from user behavior.

## Target frontend organization

Move toward this structure only as files become necessary:

```text
frontend/src/
├── app/
│   ├── providers.tsx
│   └── router.tsx
├── components/
│   ├── layout/
│   ├── shared/
│   └── ui/
├── features/
│   ├── dashboard/
│   ├── jobs/
│   ├── applications/
│   ├── interviews/
│   ├── preparation/
│   ├── skills/
│   ├── analytics/
│   ├── resume/
│   └── settings/
├── lib/
│   ├── api/
│   └── utils/
├── pages/
├── types/
├── App.tsx
└── main.tsx
```

Do not create empty directories or placeholder files solely to mirror this tree.

## Planned navigation

Use concise product terminology and group related destinations:

| Group | Destination | Route |
|---|---|---|
| Overview | Command Center | `/` |
| Recruiting | Job Inbox | `/jobs` |
| Recruiting | Applications | `/applications` |
| Preparation | Today | `/preparation` |
| Preparation | Skills | `/skills` |
| Preparation | Interviews | `/interviews` |
| Insights | Analytics | `/analytics` |
| Tools | Resume | `/resume` |
| System | Settings | `/settings` |

Use icons from the icon library already installed by shadcn. Do not add a second icon library.

## Checkpoint plan

### UI Checkpoint 1 — Design foundation and application shell

**Authorized next checkpoint. Execute this checkpoint only.**

Transform the imported demo dashboard into the reusable SWETrack shell without connecting backend data.

#### Tasks

1. Inspect the existing dashboard block and identify reusable shell components versus demo-specific sales content.
2. Add React Router if routing is not already present.
3. Create the route structure in the navigation table above.
4. Convert the sidebar navigation to SWETrack destinations and active-route behavior.
5. Create a reusable application shell containing:
   - Responsive collapsible sidebar
   - Page header
   - Breadcrumb/title area
   - Main-content container with consistent width and spacing
6. Rename the dashboard route and visible page title to **Command Center**.
7. Replace the dashboard block's sales-oriented copy, labels, and navigation with neutral SWETrack shell copy. Do not invent product metrics or populate domain screens with fake data.
8. Create restrained placeholder pages for routes other than Command Center. Each placeholder should include only:
   - Correct page title
   - One-sentence purpose based on existing product documentation
   - A clearly marked implementation-pending state
9. Establish semantic design tokens in the existing global CSS for:
   - Background and surface
   - Primary and muted text
   - Border
   - Accent
   - Success
   - Warning
   - Destructive/error
   - Informational state
10. Reuse those tokens in the shell. Do not scatter hard-coded hex colors or arbitrary state colors.
11. Preserve responsive sidebar behavior and tooltip behavior.
12. Remove demo components or data only when they are no longer imported. Do not leave dead dashboard-demo code in active bundles.

#### Out of scope

- Backend API calls
- TanStack Query or API-client generation
- Real dashboard widgets
- Feature-specific forms, tables, charts, or workflows
- Authentication
- Dark-mode implementation unless it already works from the generated block
- Backend changes
- Removal of `static/dashboard.html`

#### Acceptance criteria

- All planned routes render through client-side navigation.
- Sidebar active state follows the current route.
- Direct navigation and browser refresh work under the Vite development server.
- Mobile sidebar behavior remains usable.
- No sales-dashboard terminology remains in visible UI.
- No fake SWETrack metrics or records are introduced.
- TypeScript build, lint, and existing tests pass.
- Backend files and `static/dashboard.html` remain unchanged.

#### Suggested commit message

```text
feat(ui): establish SWETrack app shell and navigation
```

### UI Checkpoint 2 — Typed API and server-state foundation

Do not execute until Checkpoint 1 is reviewed and committed.

- Inspect FastAPI's actual OpenAPI schema.
- Add a generated or schema-derived typed API layer rather than duplicating request/response interfaces manually.
- Add TanStack Query for server-state caching and request lifecycle management.
- Add a single configurable API base URL with a local-development default.
- Configure development proxy/CORS behavior using the least invasive existing pattern.
- Provide shared loading, empty, error, and retry components.
- Prove the integration with `/health` and one read-only endpoint.
- Do not change business workflows in this checkpoint.

Suggested commit:

```text
feat(ui): add typed API client and query foundation
```

### UI Checkpoint 3 — Command Center

- Replace the remaining demo dashboard content with real data available from existing endpoints.
- Prioritize actionable information: urgent applications/deadlines, top opportunities, readiness gaps, and today's preparation.
- If a required aggregate endpoint does not exist, compose existing read endpoints only when efficient and correct; otherwise document the contract gap.
- Avoid vanity metrics and decorative charts.

Suggested commit:

```text
feat(ui): build data-backed command center
```

### UI Checkpoint 4 — Job Inbox and opportunity detail

- Build the primary Job Radar inbox with filters, sorting, pagination, freshness, eligibility confidence, source health, and application state based strictly on current API capabilities.
- Use a dense desktop table and a deliberate responsive alternative for smaller screens.
- Build an opportunity detail view or side panel showing job facts, Role Fit, Readiness, Application Priority, explanations, and available actions without conflating the scores.
- Make URL/query state shareable where practical.

Suggested commit:

```text
feat(ui): add job inbox and opportunity detail workflows
```

### UI Checkpoint 5 — Applications and interviews

- Add application pipeline views using the existing lifecycle and immutable transition history.
- Add application detail/status actions with validation and confirmation where actions are consequential.
- Add interview logging and outcome-resolution flows that accurately reflect when SkillEvents are written.

Suggested commit:

```text
feat(ui): add application and interview workflows
```

### UI Checkpoint 6 — Preparation and skills

- Build today's preparation queue with component-level study-ranking explanations.
- Add coding-practice and system-design attempt forms based on actual schemas.
- Add skill mastery views that explain BKT estimates without presenting them as certainty.
- Visualize history only where the data supports it.

Suggested commit:

```text
feat(ui): add adaptive preparation and skill views
```

### UI Checkpoint 7 — Analytics and resume tooling

- Build funnel, source-yield, response-rate, and time-to-apply views with existing non-causal caveats and sparse-data handling.
- Represent unavailable metrics as unavailable, never as zero unless zero is semantically correct.
- Add resume-tailoring UI only around currently supported operations and truth-gate constraints.
- Clearly surface validation failures for unknown, disabled, or unverified evidence IDs.

Suggested commit:

```text
feat(ui): add recruiting analytics and resume workflows
```

### UI Checkpoint 8 — Quality hardening and legacy parity

- Audit responsive behavior, keyboard navigation, labels, focus order, contrast, overflow, and long-content handling.
- Add component tests for shared interaction patterns and Playwright coverage for critical user journeys.
- Add local screenshot/visual-regression coverage for representative viewport sizes if it can remain deterministic and free.
- Test loading, empty, error, partial-data, and success states.
- Compare React functionality with the legacy static dashboard.
- Remove or retire `static/dashboard.html` only after explicit user approval and verified parity.

Suggested commit:

```text
test(ui): harden accessibility and critical workflows
```

## Required checkpoint report format

After every checkpoint, stop and return:

1. **Implemented** — concise list of completed behavior.
2. **Changed files** — created, modified, and deleted files grouped separately.
3. **Dependencies** — every dependency added or removed and why.
4. **Verification** — exact commands and summarized output for build, lint, tests, and any manual checks.
5. **Acceptance criteria** — pass/fail for every criterion in the checkpoint.
6. **Known issues** — warnings, deviations, incomplete behavior, or backend contract gaps.
7. **Git status** — exact `git status --short` output.
8. **Suggested commit message** — one conventional commit message.

Never claim a visual interaction was verified unless it was actually exercised. Never begin the following checkpoint until the user confirms that the current checkpoint was reviewed and committed.

