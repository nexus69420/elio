# Elio — Product Plan & Build Tracker

> Living checklist. Edit freely: add, remove, reorder.
> Status key: `[x]` done · `[~]` partial/stub · `[ ]` not built · `[?]` decide later

**One-liner:** Elio is a chat-first AI workspace that plans, uses your tools, asks when it should, and finishes real work — locally or with your models.

**North star:** Feel as clear as Cursor chat, as useful as a junior coworker with connectors, as trustworthy as HITL when stakes are high.

---

## 1. Who it’s for & what they should be able to do

### Primary user
Solo builder / operator who wants one place to talk to agents that can research, write, code, and act on GitHub/Slack/files — without losing control.

### Jobs to be done
| Job | User should be able to… |
|-----|-------------------------|
| Ask anything | Start a chat, pick intensity, send a goal in plain language |
| Stay in control | Require approval before risky actions; approve / modify / reject inline |
| Use their world | Connect GitHub, Slack, filesystem (and more later); see what’s connected |
| Shape agents | View/edit agent roles, tools, instructions; switch workflow packs |
| Continue work | Browse recents/tasks; reopen a thread; inspect what happened |
| Run local-first | Use Ollama (or OpenAI/Anthropic) without mandatory cloud lock-in |
| Trust the system | See status, costs, audit, traces; know when backend/LLM is down |
| Ship outcomes | Get a clear deliverable, not just chat fluff |

---

## 2. Product surfaces (UI)

### Shell
- [x] Dark/light theme
- [x] Collapsible left sidebar (animated)
- [x] Brand / New chat / nav
- [x] Recents list + search
- [x] Backend online/offline + refresh
- [~] Right Inspect pane (raw JSON — needs product polish)
- [ ] Command palette (⌘/Ctrl+K)
- [ ] Keyboard-first nav everywhere
- [ ] Multi-window / pop-out chat
- [ ] Onboarding checklist (first-run)

### Chat (home)
- [x] Empty state + starter cards
- [x] Composer (pack, intensity, ask-before-acting, send)
- [x] Thread = task prompt + deliverable + status
- [x] Inline approval cards
- [~] Title control (chevron present, no real switcher)
- [ ] Streaming tokens / live step timeline in-thread
- [ ] Edit & resend / branch chat
- [ ] Attach files / folders / URLs to a message
- [ ] @-mention agents, tools, or connectors
- [ ] Stop / cancel running task
- [ ] Retry failed step
- [ ] Pin / star / rename / archive chats
- [ ] Share read-only transcript link (later SaaS)
- [ ] Voice input (mic exists as stub)

### Tasks / runs
- [x] Task list + filters → open in chat
- [ ] Kanban or status board
- [ ] Bulk cancel / retry
- [ ] Scheduled / recurring tasks
- [ ] Run templates (“every Monday: summarize inbox”)

### Connections
- [x] Catalog enable/disable
- [x] GitHub OAuth + secrets
- [x] MCP config save/reload
- [~] Slack / filesystem (backend more ready than UX polish)
- [ ] Connection health tests per connector
- [ ] Per-connector permissions (“read-only” vs “can write”)
- [ ] OAuth for Slack / Google / Notion / Linear (expand)
- [ ] “Suggested setup” for empty workspace

### Agents
- [x] List agents + edit profile (instructions, tools, HITL, model)
- [x] Builtin presets + apply + save custom preset
- [x] Reset to defaults
- [ ] Agent gallery / marketplace (local packs first)
- [ ] Visual graph of who calls whom
- [ ] Eval scorecards per agent
- [ ] Always-on / background agents
- [ ] Multi-agent debate / parallel specialists UI

### Customize / Settings
- [x] LLM provider + models + keys + test
- [x] Actor + API token
- [x] Cost rollup, audit, tools list, semantic memory browse
- [ ] Memory manager (search, delete, pin lessons)
- [ ] Policy center (global HITL rules, allow/deny tools)
- [ ] Workspace export/import
- [ ] Notification prefs (desktop, Slack DM)

### Inspect / observability (in-app)
- [~] Trace + replay + working memory dumps
- [ ] Step timeline (plan → tools → review → deliverable)
- [ ] Diff of proposed tool args before approve
- [ ] Cost per chat / per step
- [ ] One-click open Jaeger for a task
- [ ] Failure autopsy (“why it stopped”)

---

## 3. Agents (have vs build)

### Built-in roles (exist)
| ID | Role | Purpose |
|----|------|---------|
| `supervisor` | Supervisor | Plans, routes, synthesizes |
| `research` | Research | Gather info (web, repos, docs) |
| `analysis` | Analysis | Structure findings, tradeoffs |
| `writing` | Writing | Drafts (HITL by default) |
| `code` | Code | Code changes, repro, patches |
| `reviewer` | Reviewer | Quality / risk check before final |

### Builtin packs (exist)
- [x] `research_brief`
- [x] `code_review`
- [x] `job_application`
- [ ] User-defined packs as first-class “Workflows” product surface

### Agents / packs to build (product-worthy)
- [ ] **Inbox / life admin** — email/Slack triage, drafts, reminders
- [ ] **PR coworker** — open PR, review, respond to comments
- [ ] **Incident helper** — logs → hypothesis → fix PR
- [ ] **Docs writer** — README / ADR / changelog from repo
- [ ] **Data analyst** — CSV/SQL → charts + narrative
- [ ] **Security pass** — dependency + secret scan + report
- [ ] **Onboarding buddy** — explain unfamiliar repo
- [ ] **Meeting → actions** — notes → tasks + GitHub issues
- [ ] **Browser agent** (optional) — navigate + extract with approval
- [ ] **Custom agent builder** — wizard: goal → tools → HITL → test run

---

## 4. Tools (have vs build)

### Built-in today
- [x] `web_search`
- [x] `file_read` / `file_write` (workspace sandbox)
- [x] `code_exec` (local sandbox; e2b optional)
- [x] Native GitHub subset (`whoami`, repos, issues, PRs, get_file, create_issue)
- [x] MCP bridge (demo, filesystem, github, slack servers)

### Tool gaps to close
- [ ] Parity: native GitHub = full MCP GitHub set (comment, update file, get issue)
- [ ] Reliable MCP under Windows/Celery (or drop MCP-in-worker, keep native)
- [ ] Structured tool results in chat UI (cards, not only final text)
- [ ] Tool allowlists per pack / per intensity

### Tools a best-in-class Elio should add
- [ ] Repo map / symbol search (code intelligence)
- [ ] Git CLI actions (branch, commit, PR) with HITL
- [ ] Terminal session tool (approved commands only)
- [ ] Browser / Playwright tool (HITL for navigate & submit)
- [ ] Calendar / email connectors (Google)
- [ ] Notion / Linear / Jira issue tools
- [ ] Image understand / generate (optional)
- [ ] HTTP request tool (user-defined allowlist)
- [ ] Memory write/read tools agents can call explicitly
- [ ] “Ask user” tool (structured questions mid-run)

---

## 5. Connectors

### Exist
- [x] GitHub (OAuth + PAT fallback)
- [x] Filesystem
- [x] Slack
- [x] Demo

### Should build (phased)
- [ ] Google (Gmail, Calendar, Drive) — OAuth
- [ ] Notion
- [ ] Linear / Jira
- [ ] Discord
- [ ] Postgres / DB read-only
- [ ] Sentry / Datadog (read incidents)
- [ ] Figma (read)
- [ ] Generic OpenAPI / webhook connector
- [ ] “Local folder as project” first-class (beyond generic FS)

---

## 6. Core platform features

### Orchestration
- [x] LangGraph workflow (memory → plan → execute → review → synthesize → HITL → persist)
- [x] Celery worker + Redis + Postgres
- [x] Intensity → HITL / depth mapping (`quick` / `assist` / `work` / `deep`)
- [ ] True streaming of plan/tools/tokens to UI (SSE/WebSocket)
- [ ] Parallel specialist fan-out with merge
- [ ] Human “take over” path in UI
- [ ] Pause / resume / cancel
- [ ] Budgets (max $ / max steps / max time) enforced

### HITL & trust
- [x] Plan + tool + final gates
- [x] Inline approve / modify / reject
- [ ] Take over in UI
- [ ] Policy rules (“never push”, “always ask before email”)
- [ ] Approval history per chat
- [ ] Risk labels on proposed actions

### Memory
- [x] Working memory (Redis)
- [x] Semantic memory (Chroma)
- [~] Browse in Settings
- [ ] Chat-scoped vs workspace-scoped memory UX
- [ ] Forget / edit memories
- [ ] “Remember this” explicit user action
- [ ] Project memory packs (per repo)

### Models
- [x] Ollama / OpenAI / Anthropic / stub
- [x] Settings UI + test
- [ ] OpenRouter / Azure / local LM Studio presets
- [ ] Per-agent model overrides that “just work”
- [ ] Model router (cheap for plan, strong for code)

### Observability
- [x] OTel → Jaeger
- [x] Traces, replay, costs, audit APIs
- [~] Exposed roughly in Inspect/Settings
- [ ] Product-grade run debugger
- [ ] Optional LangSmith polish

### Security & tenancy
- [x] Optional API token + actor header
- [ ] Real auth (email magic link / OIDC) — when leaving single-workspace
- [ ] Workspaces / orgs / roles
- [ ] Secrets vault UI
- [ ] Audit export
- [ ] Sandbox hardening review

---

## 7. What a user can do today (honest)

1. Open Elio, connect backend (Docker), optionally connect GitHub.
2. Start a chat; choose intensity + pack; toggle ask-before-acting.
3. Send a goal; watch task status; approve risky steps inline.
4. Read the deliverable; open Inspect for memory/trace dumps.
5. Browse Tasks / Recents; reopen work.
6. Edit agents & presets; change LLM provider; scan costs/audit/tools/memory.

---

## 8. What a user should be able to do (target)

1. **One prompt → finished artifact** (PR, doc, issue set, report) with clear steps visible.
2. **Never fear surprise writes** — approvals are obvious, editable, and fast.
3. **Bring their stack** — GitHub/Slack/files first; Google/Notion/Linear next.
4. **Teach Elio** — save packs, pin memories, tune agents without YAML pain.
5. **Debug any failure** in under a minute (timeline + tool I/O + retry).
6. **Stay local** when they want; use cloud models when they choose.
7. **Come back tomorrow** — scheduled runs, pinned chats, project contexts.

---

## 9. Suggested build phases (for tracking)

### Phase A — Solid MVP (trust + clarity)
- [ ] Streaming run timeline in chat
- [ ] Stop/cancel task
- [ ] Polish Inspect (timeline, not JSON walls)
- [ ] Approval `take_over` + better modify UX
- [ ] GitHub tool parity + MCP/Windows reliability
- [ ] Fix first-run: empty connectors → guided connect
- [ ] Stable Docker story (health green, UI port docs)

### Phase B — Daily driver
- [ ] Attachments + @ mentions
- [ ] Rename/pin/archive chats
- [ ] Memory manager
- [ ] Policy center (global HITL rules)
- [ ] PR coworker + Docs writer packs
- [ ] Slack connector UX complete
- [ ] Budgets (steps/$/time)

### Phase C — Differentiated workspace
- [ ] Always-on / scheduled agents
- [ ] Browser tool (HITL)
- [ ] Google connector set
- [ ] Visual agent graph + evals
- [ ] Project-scoped workspaces (multi-repo)
- [ ] Command palette + power keyboard UX

### Phase D — Productize (only if going beyond single-tenant)
- [ ] Auth, billing, multi-workspace
- [ ] Share / collaborate
- [ ] Hosted cloud offering
- [ ] Pack marketplace

---

## 10. Explicit non-goals (for now — edit if you disagree)

- [?] Multiplayer editing of the same live agent run
- [?] Fully autonomous unbounded internet agent with no HITL
- [?] Replacing the IDE (Elio complements Cursor; doesn’t become VS Code)
- [?] Training custom foundation models
- [?] Mobile-native app (responsive web is enough initially)

---

## 11. Tracking scratchpad

**Next 3 picks (you fill):**
1. …
2. …
3. …

**Cut list (you fill):**
- …

**Open questions:**
- Local-only forever vs path to hosted SaaS?
- How aggressive should default HITL be?
- Is “always-on agents” core or later?
- Browser agent: in or out of MVP?

---

*Generated as a working inventory + aspiration list for Elio. Treat statuses as starting points — correct anything that’s wrong as you edit.*
