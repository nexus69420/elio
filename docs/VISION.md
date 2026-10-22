# Elio product vision

Elio is an everyday AI assistant with chat as its primary interface. It should help people move from an intention to a finished outcome across personal tasks, information work, and technical work.

Ask naturally, provide the context and connections it needs, follow its progress, and continue the conversation as the work changes. Specialized agents and tools make that possible without requiring the person to design an agent workflow for every request.

## The experience we are building

1. **Ask for an outcome.** Start with a question, instruction, file, or existing conversation.
2. **Work at the appropriate scale.** Answer simple questions directly; plan and use tools or specialists when needed.
3. **Stay informed and in control.** Explain the current step, surface results, and request approval before actions that require it.
4. **Deliver something useful.** Return an answer, draft, artifact, or completed action with a clear account of what succeeded and what remains.
5. **Continue over time.** Understand follow-ups, retain relevant context, and eventually handle reminders and recurring work.

This is the target experience. The prototype currently executes isolated task runs through a chat interface.

## Everyday capabilities

| Area | Intended outcomes |
|------|-------------------|
| Research and decisions | Gather evidence, compare options, answer questions, produce briefs |
| Writing and documents | Draft, revise, summarize, organize information |
| Personal admin | Triage an inbox, prepare replies, manage reminders, help with calendar work |
| Team communication | Summarize messages and turn meeting notes into actions |
| Coding and operations | Understand repositories, review changes, prepare docs, investigate problems |
| Data and files | Work with supplied files/data to produce analyses and artifacts |
| Recurring work | Run an agreed task on a schedule and report useful results |

These areas guide expansion. They are not shipped-feature claims or a commitment to implement every connector at once.

## Product principles

- **One coherent conversation.** Context and outcomes survive follow-ups and reopening a chat.
- **Choose capabilities for the work.** Simple questions need not enter the full specialist pipeline; complex work can use suitable agents and tools.
- **Complete useful tasks.** Connected actions have visible results; drafts and proposed actions are clearly identified.
- **Make actions understandable.** Show proposed writes before approval, respect rejection, and make failures actionable.
- **Build trust through evidence.** Show sources, results, execution state, and what was actually verified.
- **Keep memory manageable.** Conversation context and longer-term memory serve different purposes. People can inspect and control what persists.
- **Offer model choice.** Preserve a local path and optional cloud providers.
- **Grow through integrations.** Expand around useful user journeys with explicit permissions and health checks.

## First milestone: a conversation that gets work done

A continuing conversation should perform one useful connected task, show progress and tool results, ask for approval when needed, and retain the outcome for follow-up.

For example: summarize issues from a connected GitHub repository, refine the summary in the same conversation, and draft or create a follow-up issue. Creation must show the proposed action and wait for approval; rejection must leave the external repository unchanged.

GitHub is a practical initial integration because code already exists. Elio's intended scope includes everyday work beyond software development.

See the [roadmap](../ELIO_PRODUCT_PLAN.md) for acceptance criteria and later capability areas.

## Decisions still open

The initial user segment, first personal-admin integration, default autonomy rules, and hosted product model still need concrete decisions. Scheduling, browser work, voice, and broader connections are expansion areas; their order depends on a reliable conversational task foundation.

The implementation is a single-workspace prototype. Hosted accounts, billing, collaboration, a marketplace, and native mobile clients have no committed release scope.
