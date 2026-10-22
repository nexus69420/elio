# Elio product plan

Updated 22 October 2026.

**Direction:** an everyday AI assistant that uses tools and specialized agents through a continuing chat to complete useful work across a person's apps and information.

The [vision](docs/VISION.md) explains the intended experience. This plan separates code that exists from work still required. “Exists” means present in source, not verified in a running environment. All milestones below are planned; this documentation update does not implement them.

## Current implementation baseline

| Area | Present in the code | Gap to the intended experience |
|------|---------------------|--------------------------------|
| Chat and tasks | Composer, task list, recents, prompt/result views | Every message creates an isolated task; no persisted conversation/message model |
| Execution | Celery jobs and LangGraph plan/execute/review | Fixed pipeline, sequential specialists; no direct-answer routing or dependency-aware fan-out |
| Progress | Task/approval polling, traces, replay, Inspect | No streamed timeline or tokens; no cancellation API |
| Approvals | PostgreSQL records, Redis notifications/polling, inline approve/modify/reject | Selected actions gated; built-in file writes ungated; final approval occurs after tools |
| Agents | Supervisor, research, analysis, writing, code, reviewer; profiles and presets | Everyday task categories, capability selection, and agent evaluations |
| Tools | Search, workspace files, Python execution, native GitHub subset, MCP | Structured results, consistent permissions, reliability, broader integrations |
| Connections | GitHub OAuth/PAT; MCP demo/filesystem/GitHub/Slack configuration | Connection health/permissions and personal-admin connectors |
| Memory | Redis working memory and workspace-wide Chroma lessons | Conversation context and memory inspection/edit/forget controls |
| Models | Ollama, OpenAI-compatible, Anthropic, stub, editable settings | Verified provider/model combinations and task-aware routing |
| Diagnostics | Audit, transcripts, estimated costs, OpenTelemetry/Jaeger | User-facing failure explanations and enforced budgets |
| Controls | Packs and Quick/Assist/Work/Deep labels | Intensity primarily changes approval settings, not execution depth/budgets |

## Milestone 1: continuing chat with reliable connected work

**Outcome:** work through a task over multiple messages, see what Elio is doing, approve a proposed action, and reopen the conversation with its context intact.

### Conversation foundation

- [ ] Persist conversations and ordered user/assistant messages separately from task runs.
- [ ] Associate runs, approvals, and results with their conversation and initiating message.
- [ ] Append follow-ups to the selected conversation; New chat starts a separate context.
- [ ] Supply relevant history to the runtime with explicit context limits.
- [ ] Reopen a conversation after refresh/restart without losing messages or completed outcomes.
- [ ] Define behavior for messages sent while a run is active; preserve ordering and avoid accidental duplicate work.
- [ ] Keep existing task records accessible when introducing conversations.

### Visible execution and control

- [ ] Display an ordered timeline of plans, steps, tool calls/results, approvals, and terminal outcomes.
- [ ] Deliver live progress events and recover the timeline after reconnecting.
- [ ] Support cancellation with an explicit terminal state. Prevent further actions once cancellation is acknowledged; show actions already completed or in flight.
- [ ] Keep task listing read-only; determine failures from execution evidence rather than polling-time guesses.
- [ ] Define retry/recovery behavior so failures and duplicate job delivery do not silently repeat external writes.

### Consistent approvals

- [ ] Enforce approval before execution for writes covered by the user's policy, including built-in file writes.
- [ ] Show the target, action, and proposed arguments; validate edits and recheck permissions before execution.
- [ ] Preserve rejection and approval history. Final-answer approval must not substitute for permission to execute an earlier action.
- [ ] Resume pending approvals across API/worker boundaries and recover explicitly from interruption.

### First connected journey and acceptance criteria

Use the existing GitHub integration to summarize repository issues, refine the summary in the same conversation, and propose a follow-up issue. GitHub is the initial integration; the product direction includes everyday work beyond software development.

This milestone is complete when:

1. Follow-ups correctly use earlier messages and tool results without requiring the user to restate context.
2. Refreshing/reopening restores messages, run status, completed results, and pending approvals.
3. A proposed issue write waits for approval; rejection causes no write; approval executes the displayed action once.
4. Progress and a clear result or actionable error are visible. Cancellation prevents subsequent actions once acknowledged.
5. Failure/restart checks cover persistence, approval resolution, external-write duplication, and recovery.
6. The journey passes integration checks with fixtures or explicitly designated test resources, followed by browser verification. The validation record identifies live dependencies and side effects.

## Milestone 2: useful everyday tasks

**Outcome:** support repeated personal and information work beyond the first technical integration.

- [ ] Select and validate a first personal-admin integration, such as email or calendar.
- [ ] Research/writing journeys with sources and reusable drafts/artifacts.
- [ ] Inbox triage and reply drafts; meeting notes to actions.
- [ ] File/URL attachments and conversation-scoped context.
- [ ] Connection health checks and understandable read/write permissions.
- [ ] Rename, search, pin, and archive conversations.
- [ ] Inspect, edit, and forget longer-term memories separately from chat history.
- [ ] Reusable workflows/custom agents without manual graph configuration.
- [ ] Direct answers for simple requests and suitable specialists for complex work.
- [ ] Enforced step/time/cost budgets; intensity controls with actual runtime effects.

Choose concrete user journeys before expanding the connector catalog. Each needs a clear input, permissions, deliverable, and failure path.

## Milestone 3: work over time

**Outcome:** carry out agreed background and recurring work with visible history and user control.

- [ ] Reminders and scheduled/recurring tasks with timezone-aware scheduling.
- [ ] Persistent schedules, cancellation, missed-run behavior, and duplicate-run protection.
- [ ] Notifications that distinguish useful results, failures, and required user action.
- [ ] Background agents with bounded permissions and execution budgets.
- [ ] Project contexts and optional parallel specialists with dependency handling.

## Capability backlog

These extend the everyday-assistant direction; their ordering is not a release commitment.

| Area | Candidates |
|------|------------|
| Agents/workflows | Personal admin, researcher, writer, data analyst, meeting assistant, PR coworker, incident helper, docs writer, onboarding helper, security review |
| Connections | Gmail/Calendar/Drive, Notion, Linear/Jira, Discord, database readers, Sentry/Datadog, Figma, OpenAPI/webhooks |
| Tools | Browser interaction, repository/symbol search, Git/terminal actions, HTTP requests, explicit memory tools, structured questions to the user |
| Media/context | Images, voice input, richer files/artifacts, local folders as projects |
| Workspace | Command palette, keyboard navigation, onboarding, notifications, export/import, shareable transcripts |
| Quality | Step-level costs, proposed-action diffs, failure explanations, agent scorecards, connector/tool evaluations |
| Platform | Provider presets, model routing, secret handling, authentication/roles if expanding beyond one workspace |

## Working rules

- Update implementation status when behavior exists and its validation is recorded; mark partial integration explicitly.
- Reassess scope around complete user journeys rather than the number of tools/agents added.
- Preserve the single-workspace/local model path while hosted deployment and commercial scope remain undecided.
- Accounts, billing, collaboration, a marketplace, and native mobile clients have no committed release scope.
- Use the [development guide](docs/DEVELOPMENT.md) for current setup and verification limits.
