# GameForge AI — AI Development Constitution

## Purpose
This file is the highest-priority instruction for AI coding agents working on GameForge AI.

GameForge AI is an AI-powered game discovery and game-prototyping platform with two core capabilities:
1. Discover existing games from natural-language descriptions.
2. Turn a natural-language game idea into a simple playable browser prototype.

The current repository contains a polished frontend-only prototype. Backend, AI, discovery, and real prototype-generation functionality are future phases.

## Non-Negotiable Rules

### Preserve the finished frontend
The existing frontend visual design is frozen unless the current task explicitly requests a visual change. Stitch/reference screens and `DESIGN.md` are the visual source of truth. Do not redesign layouts, colors, typography, or invent primary screens.

### Exactly seven primary routes
- `#/`
- `#/discover/no-matches`
- `#/build`
- `#/status/success`
- `#/status/error`
- `#/dashboard`
- `#/profile`

Do not create another primary route without an explicit product/architecture decision.

### Approved initial technology
Frontend: React, TypeScript, Vite, Tailwind CSS, react-router-dom, React Context.
Backend: Python, FastAPI, Pydantic, SQLAlchemy, SQLite, Alembic.
AI: Hosted LLM API (local LLM inference unsupported per ADR-006), structured output, Pydantic validation.
Discovery: Sentence Transformers, FAISS, normalized catalog.
Runtime: Phaser.
Transport: REST + SSE for build logs.

Do not replace technologies merely because another is fashionable.

### Avoid premature complexity
Do not introduce without an approved ADR: Celery, Redis, Kafka, GraphQL, LangChain, LlamaIndex, Kubernetes, microservices, service meshes, cloud gaming infrastructure, or other major orchestration systems.

### AI safety boundary
Never implement `LLM -> arbitrary JavaScript -> browser execution`. The intended pipeline is natural language -> intent/specification -> Game DSL -> schema validation -> repair/retry -> artifact -> Phaser runtime.

### Backend ownership
When backend integration is complete, backend/database are authoritative for persistent business state. A successful backend build creates/persists its project as part of the server-side build lifecycle.

### Phase discipline
Read `docs/11-IMPLEMENTATION-PHASES.md`. Do not implement future phases early. If a request belongs to a later phase, stop and report it.

## Documentation Authority
1. Accepted ADR
2. Current source code for current implementation facts
3. Product specification
4. System architecture
5. Current status
6. Other docs
7. Old reports

If meaningful sources conflict and the conflict cannot be resolved, stop and report it.

## Change Discipline
For cross-cutting architecture changes, update the relevant ADR, architecture docs, status doc, then implement and test.

## Security Rules
Never hardcode secrets, expose provider credentials to frontend, trust unvalidated LLM output, execute arbitrary generated code, expose stack traces, or use wildcard production CORS.

## Testing Rules
Distinguish code verified, command verified, statically inferred, browser verified, and not verified. Never claim a browser test passed because source code looks correct.

## Current Frontend Baseline
The current frontend uses a single `AppContext`, localStorage key `gameforge_ai_state`, and a temporary mock build machine: `IDLE -> COMPILING -> SUCCESS/ERROR`. The temporary deterministic failure test is the case-sensitive `/\bERROR\b/` (backend `game_generation_service.py`) — case-sensitive specifically so ordinary lowercase "error" in a legitimate prompt does not false-positive.

## Git Checkpoint Policy
Git checkpoints are mandatory at the end of EVERY approved implementation phase.

When a phase reaches its exit criteria:
1. Run the required tests.
2. Run the required builds.
3. Review `git diff`.
4. Review `git status`.
5. Confirm only intended files are changed.
6. Update required documentation/status files.
7. Create ONE logical Git commit for the completed phase.
8. Verify the commit exists.
9. Verify the working tree is clean.
10. Report the commit hash.

Do NOT proceed to the next phase before this checkpoint is complete.

### Commit rules
- One logical commit per completed phase.
- Commit message must clearly identify the phase.
- Do not mix unrelated changes into a phase commit.
- Do not reset/discard user work.
- Do not rebase unless explicitly requested.
- Do not force-push.
- Do not rewrite previous phase history.
- Do not commit secrets, `.env`, databases, virtual environments, caches, build artifacts, or generated temporary files.
- If a phase fails its verification, DO NOT create a "complete" checkpoint.
- If the working tree contains unrelated user changes, STOP and report them before committing.

### Standard phase commit format
Use:
`<area>: <phase-specific summary>`

Examples:
- `backend: establish FastAPI foundation`
- `backend: add project persistence and CRUD API`
- `backend: add build jobs and SSE`

### Checkpoint is part of phase completion
A phase is NOT considered COMPLETE until:
- implementation complete,
- tests pass,
- documentation updated,
- Git commit created,
- working tree verified clean.

The final report MUST include:
- commit hash
- commit message
- `git status` result
- tests
- build result

## Task Execution Ledger Policy

### Applicability
The Task Execution Ledger Policy is a mandatory workflow rule for every substantial:
- implementation phase
- feature
- bug-fix batch
- architectural change
- migration
- integration task
- QA / audit task
- documentation migration

Every such task MUST maintain:
`TASK.md`
at the repository root.

### Canonical File Location
The canonical ledger file is:
`<repository-root>/TASK.md`

Do NOT create separate canonical task ledgers in subdirectories (`backend/TASK.md`, `gameforge-ai/TASK.md`, `src/TASK.md`) unless a future project-level architecture decision explicitly requires them. While complex tasks may generate auxiliary planning documents, root `TASK.md` remains the authoritative execution ledger.

### Execution Ledger vs Scratchpad
`TASK.md` is the persistent source of truth for the CURRENT AI task. It is an execution ledger, NOT a chain-of-thought scratchpad.

It MUST NOT contain:
- private chain-of-thought or conversational musings
- hidden reasoning
- passwords, API keys, access tokens, credentials, or secrets
- sensitive personal information

It SHOULD contain only concise, verifiable project state:
- task name & objective
- ordered checkable subtasks
- standard status values
- files modified/created
- commands executed
- automated tests & browser verification results
- design/architecture decisions
- blockers & unblocking criteria
- remaining work
- Git checkpoint details

### Canonical Task Lifecycle
Every substantial AI task MUST follow this lifecycle:
```text
READ DOCUMENTATION
      ↓
INSPECT REPOSITORY
      ↓
CHECK GIT STATUS
      ↓
CREATE / UPDATE TASK.md
      ↓
BREAK WORK INTO CHECKABLE SUBTASKS
      ↓
IMPLEMENT ONE SUBTASK
      ↓
VERIFY THAT SUBTASK
      ↓
RECORD EVIDENCE
      ↓
MARK SUBTASK COMPLETE
      ↓
MOVE TO NEXT SUBTASK
      ↓
FINAL AUDIT
      ↓
UPDATE DOCUMENTATION
      ↓
GIT CHECKPOINT
      ↓
VERIFY CLEAN WORKING TREE
      ↓
MARK TASK COMPLETE
```

### Standard Status Values
Every task and subtask MUST use exactly one of the four standard status values:
- `NOT_STARTED`
- `IN_PROGRESS`
- `BLOCKED`
- `COMPLETE`

Do not invent arbitrary variants such as `DONE`, `FINISHED`, `PARTIAL`, `COMPLETE-ish`, etc.

### Subtask Completion Rule
A subtask may be marked `COMPLETE` only after:
1. implementation is finished,
2. required verification is performed, and
3. concrete evidence is recorded in `TASK.md`.

"The code looks correct" is NOT sufficient evidence. Concrete evidence (files modified, test commands run, actual test counts and outputs) is mandatory.

### Blocked Task Rule
If a subtask cannot proceed:
- set Status = `BLOCKED`
- record in `TASK.md`:
  - exact blocker description
  - what was attempted
  - what is required to unblock it

Do not silently skip blocked work or mark blocked work `COMPLETE`.

### Interruption and Resumption Rule
If an AI session ends, crashes, times out, is manually interrupted, or is handed over to another AI agent, the FIRST required action when resuming is:
`READ TASK.md`

Then:
1. identify the active task and current subtask,
2. identify the first incomplete or blocked required item,
3. inspect the recorded evidence,
4. resume work directly from that point without repeating completed work.

Future AI agents MUST NOT rely solely on conversational memory for task state.

### Evidence Requirements
Evidence recorded in `TASK.md` must be concrete:
- **Files**: Exact relative or workspace paths of touched files.
- **Commands**: Exact command lines executed (`pytest -q`, `npm run build`, `npx tsc --noEmit`).
- **Results**: Real pass/fail counts, exit codes, or verification outputs.
- **Browser Testing**: Record specific viewport dimensions (375x812, 768x900, 1440x900) and user flows tested. If browser testing was not performed, explicitly record: `BROWSER TESTING: NOT PERFORMED`. Never claim browser verification without performing it.

### Standard TASK.md Format
Every substantial task ledger should follow this structure:
```markdown
# GameForge AI — Task Execution Ledger

## Task
<phase / feature / task name>

## Status
IN_PROGRESS

## Objective
<clear objective>

## Started
<YYYY-MM-DD>

---

## 1. Pre-Implementation

- [ ] Read AGENTS.md
- [ ] Read relevant documentation
- [ ] Inspect current source
- [ ] Inspect git status
- [ ] Check for unrelated/uncommitted user changes

### Evidence
...

---

## 2. Implementation

- [ ] Subtask A
- [ ] Subtask B
- [ ] Subtask C

### Evidence
...

---

## 3. Verification

- [ ] Unit tests
- [ ] Integration tests
- [ ] Browser tests where required
- [ ] TypeScript/type checking
- [ ] Production build
- [ ] Console audit

### Results
...

---

## 4. Documentation

- [ ] Architecture documentation updated
- [ ] Current status updated

---

## 5. Git Checkpoint

- [ ] git diff reviewed
- [ ] git diff --stat reviewed
- [ ] secrets checked
- [ ] generated artifacts checked
- [ ] commit created
- [ ] working tree clean

Commit:
...

---

## Remaining Work
...

## Blockers
...

## Change Log
...
```

### Overall Task Completion Rule
A substantial task may be declared `COMPLETE` only when:
- [x] every mandatory subtask is `COMPLETE`
- [x] all required tests pass
- [x] required browser tests actually occurred (or explicit non-applicability recorded)
- [x] documentation is updated
- [x] no blocking issue remains
- [x] Git checkpoint is complete
- [x] working tree is clean

If any mandatory item remains, the overall task status MUST NOT be marked `COMPLETE`.

### Git Policy Integration
`TASK.md` supplements and enforces the Git Checkpoint Policy. The completion of every substantial task requires reviewing `git diff`, `git diff --stat`, `git status`, verifying zero secrets or extraneous build artifacts, creating one logical commit, and confirming a clean working tree. Never force-reset, discard user changes, force-push, or rewrite history without explicit user instruction.

### Task File Lifecycle
`TASK.md` remains in the repository after task completion as project history. Do NOT silently delete completed task history. The next substantial task updates/reuses `TASK.md` by cleanly recording the new active task while retaining a concise change log and links/references to previous phase records, keeping the file structured and readable without unbounded transcript bloat.

## End-of-Task Requirement
Every AI coding task must report: what changed, why, what was verified, what was not verified, documentation/ADR impact, and whether the next phase is allowed.
