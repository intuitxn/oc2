# Intuitxn Labs — OpenCode ACP workspace

Open http://127.0.0.1:4100. Labs starts OpenCode directly with `opencode acp --cwd <directory>` and speaks ACP v1 over newline-delimited JSON-RPC. Agent Manager and tmux are not dependencies. All new chats and scoped sessions use OpenCode.

## Sessions

Start a chat with one prompt. Replies call `session/prompt`; assistant updates and tool activity are stored locally and displayed in the conversation. Tool permission requests show explicit choices in the UI. The ACP process requests permission for tools; Labs never automatically approves a request. Cancel interrupts the turn. Resume loads the existing OpenCode session with `session/load`; it does not repeat the previous prompt. Interrupted work requires an explicit new message.

Each session has a dedicated ACP process, working directory, durable local ID, underlying OpenCode session ID and event history. Labs chooses the authenticated `opencode-go/deepseek-v4-flash` model. Credentials remain in the existing OpenCode profile; inherited secret environment variables are excluded from the process environment. The runtime can access local resources under its own existing profile and tool permissions; this is not an OS sandbox.

The tree groups sessions by path and parent. `+ child` starts a fresh conversation in the parent's directory. Use work ops for an isolated worktree and selected context fork. Session replay on load is suppressed in Labs' event history to avoid duplicate output. Service restart marks an unfinished turn interrupted instead of resubmitting it. Existing Agent Manager metadata is retained in its old database tables and is not used for new sessions.

## Scoped work and review

Open **work ops** beside a conversation. Create a feature with an absolute repository path, objective, acceptance criteria, allowed relative paths and verification commands. Commands are argument arrays, e.g. `[["npm","test"]]`; they execute with the local user's authority. A work branch gets its own Git worktree. Scope validates candidate changes; it does not sandbox execution.

**Start scoped session** sends the feature brief directly through ACP in that worktree. The durable binding prevents duplicate starts. An uncertain binding can be reconciled by linking the matching ACP worktree session. Resume loads a stopped bound session. Active turns and outstanding permissions block candidate verification and landing.

Save selected context as a checkpoint. Fork branches from the parent's candidate or base with selected context and a new objective. Merge selected decisions appends an accepted selection with source-work, candidate and context-hash provenance. Export emits `labs.work-context/v1`; remote execution and credential transfer are not implemented.

Snapshot records a scoped candidate commit. Verify integrates it with the current target in an isolated review worktree and runs the configured checks. At least one successful check is required. Checks that alter the integration fail verification. Inspect candidate and integration diffs and receipts, then approve the exact digest. Merge is separate and requires the same candidate, integration, target and a clean owning checkout. No automatic push occurs. Approval means the local operator's action, not a multiuser signature or model claim.

Conflicts retain the integration worktree. Resolve and stage them there, then **verify resolved conflicts**, review and approve again. Changed code, moved targets and merged context invalidate reviews. Labs serializes its own operations; unrelated external Git processes are outside that lock.

## Nudge and operation

Nudge programs calls the installed `telepathy-program` catalog, compiler and allowlisted runner. These actions neither publish artifacts nor activate learning changes; those reviewed effects remain in Telepathy.

Run `python3 script/labs/install.py` to snapshot source into private runtime state and install the user LaunchAgent `intuitxn.labs-workspace`. Re-run after source changes. It starts after user login, listens on loopback port 4100, and does not depend on an active terminal manager. The public Labs website remains separate.

Run tests from this directory with `python3 -m unittest -v`; verify browser JavaScript with `node --check app.js`. Git tests use disposable repositories. ACP tests exercise framing, permissions, durable state and interrupted-turn behavior; live execution evidence should distinguish protocol success from model quality or human acceptance.

Live verification on 2026-09-08: a browser-created chat returned `LABS_ACP_READY` through the installed OpenCode ACP process. After service restart, the same remote session loaded and accepted a new prompt with prior conversation preserved. The UI surfaced a real read permission and submitted an explicit rejection. Separate direct ACP probes verified both rejection and allow-once with completed tool execution. Twenty-seven tests passed, including five transport/session tests. Typed success is not a quality evaluation.
