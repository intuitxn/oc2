# Intuitxn Labs

The existing Labs UI is now a chat-first interface over Agent Manager. Open
`http://127.0.0.1:4100` after running `sh script/oc2-labs.sh workspace`.

- One session tree, selected conversation, and inline prompt bar.
- Names, statuses, group paths, and screen output come from Agent Manager.
- Click a chat to read and reply. Replies go through the manager's delivery queue.
- `+ chat` starts a real agent from one prompt, using Codex or OpenCode.
- Group paths such as `labs/design` create nested navigation when spawning.
- `make root` focuses the tree on any chat and its children; `/ root` returns.
- `+ child` starts a **fresh conversation**, inheriting the selected chat's directory.
  It does not fork or copy the parent's transcript. Parent links persist locally.
- `n` starts a chat, `/` finds one, Space focuses the prompt; Enter sends and
  Shift+Enter inserts a newline. Arrows navigate/fold the tree.
- Archived is a read-only view. It does not stop or archive any running process.

No dashboard, product cards, mandatory task lifecycle, or creation dialogs.
The earlier draft-thread data remains in SQLite for preservation, but is no longer
the interaction model. Agent Manager owns sessions and message delivery; SQLite
only adds parent navigation metadata for chats created through this interface.

The server stays loopback-only with Host/Origin checks and a static asset allowlist.
No runtime data is copied into the public Labs root. Public/shared deployment is
not included. Agent Manager must be available in the server's environment.

Tests: `cd script/labs && python3 -m unittest -v`; client syntax: `node --check app.js`.
Live read and navigation can be verified without sending prompts or spawning agents.

## Scoped work, context and review

Open **work ops** beside a conversation. Create a feature with an absolute repository path, objective, acceptance criteria, allowed file/directory paths and verification commands. Commands are explicit argument arrays, for example `[["npm","test"]]`; they execute locally with the user's authority. Work is isolated in a Git worktree. Scope validates candidate paths; it does not sandbox the agent or commands.

Start scoped session attaches a real Agent Manager session to that worktree; its start receipt persists. Unknown delivery cannot spawn twice: link the matching worktree session to reconcile it. Resume operates on an existing stopped session. Session output remains owned by Agent Manager. A linked active/starting/waiting session blocks snapshot, verification and landing until it rests. Agent Manager process/session creation does not prove the agent executed its brief.

Save selected context as a checkpoint. Fork creates a new worktree and objective from the parent's candidate or base, with explicitly selected context. Merge selected context appends an accepted selection with source-work, candidate and context-hash provenance; it does not copy the entire transcript. Export emits `labs.work-context/v1` selected context for transfer. There is no automatic remote executor or credential transfer.

Snapshot records a scoped candidate commit. Verify integrates it with the current target in a separate review worktree and runs the declared checks. At least one successful check is required; changed files or commits produced by checks invalidate verification. Inspect candidate and integration diffs plus receipts, check the review box, and approve the exact digest. Merge is a separate action and requires the same candidate, integration, target, review and a clean owning checkout on the target branch. No automatic push occurs. Approval denotes the local operator, not an authenticated multiuser signature or an agent's claim.

Conflicts retain the review worktree. Resolve and stage them there, then choose **verify resolved conflicts**, inspect the resulting integration and approve again. Stale code, changed targets and merged context invalidate review. This is bounded recovery with explicit review, not unrestricted autonomous merging. Labs serializes its own Git operations; unrelated external Git processes are outside its application lock. Don't concurrently mutate the target checkout during landing.

Nudge programs lists the installed `telepathy-program` catalog. Compile and Run call its allowlisted typed host. Inputs/results and receipts are visible; neither action publishes artifacts or activates learning changes. Artifact publication and reviewed learning activation remain in Telepathy.

## Install and verification

`python3 script/labs/install.py` snapshots source into private runtime state and installs the `intuitxn.labs-workspace` user LaunchAgent on port 4100. Re-run after source changes. It binds to the current Agent Manager session environment; after replacing the manager instance, reinstall from that manager. The service runs after user login and is loopback-only. It is not exposed on the public Labs website.

Tests use real disposable repositories for scope, symlink rejection, hidden staged changes, stale candidates/targets, failed or mutating checks, conflict repair, selected context merge, and digest-bound landing. Manager command tests cover literal message delivery, worktree assignment and duplicate-start prevention. Browser verification on 2026-09-08 created an isolated feature, spawned a manager session, and reviewed a fixture candidate with a successful configured check. The spawned OpenCode session returned no screen output and its follow-up remained queued; it was stopped after verification. The fixture change was prepared by the test operator, not credited to that session.
