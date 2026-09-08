# Nodes — the opencode2 design principle

One runtime, everything a plugin, humans accept.

## Invariants

1. **`opencode` is always the latest local build.** `~/opencode2` is the source of
   truth; `dist/` is the binary; the wrapper at `~/.local/bin/opencode` runs the
   dist binary against the canonical profile. No brew copy, no second CLI.
2. **Everything is a plugin.** Agents (nodes), runtimes (harness adapters), the
   network surface (buzz), updates, and programs (nudge) are all plugins loaded
   from the profile's `config/opencode/plugin/*.ts`. The runtime core is never
   forked for behavior we want.
3. **Agents are charters plus a map.** Charters live in `config/opencode/agent/*.md`
   (mode, description, prompt). The delegation graph lives in `plugin/nodes.ts`
   as data. A node delegates to subagents; a node may declare a non-default
   runtime harness (codex today, others tomorrow) without changing the charter.
4. **Humans accept.** Every plugin tool that reaches the network drafts instead of
   sends. Publishing, accepting, resolving are human actions. `permission.ask`
   gates anything destructive.
5. **Updates are part of the design.** `oc2-update` pulls + builds `~/opencode2`
   and the plugin set, and drafts a dated changelog entry. The changelog is
   posted to the buzz `changelog` channel only from an environment that holds
   the owner's key — the plugin never reads, prints, or stores it.

## Topology

```
human (buzz) ──> buzz network (relay)
                    │  /intuitxn jobs + thread replies
                    v
        opencode2 node (this machine)
          primary: @telepathy ── routes ──> @atlas @forge @ledger @scout @diplomat @pilot
          plugins: nodes | runtimes | buzz | updates | nudge
                    │
                    ├─ runtime: opencode (self, default)
                    ├─ runtime: codex exec --json (sandboxed worker)
                    └─ runtime: <future adapters>
```

buzz Nest agents (Pollen, Fizz, Honey) remain optional conversational helpers,
drafted and dormant by team decision; the single desk/opencode2 node is the
execution truth. Their pairing table lives in `~/.buzz/PLANS/BUZZ_AGENT_PROMPTS.md`.

## Layout

| Path | Role |
|---|---|
| `~/opencode2` | source, build scripts, specs (this file) |
| `~/opencode2/packages/opencode/dist/opencode-darwin-arm64/bin/opencode` | latest build |
| `~/.local/bin/opencode` | wrapper: latest build + canonical profile |
| `~/.opencode2-profiles/work` | canonical profile (config/data/cache/state) |
| `~/.opencode2-profiles/smoke`, `work2`, `relay` | test cells — disposable |
| `~/.opencode2-profiles/work/config/opencode/plugin/` | the plugin set |
| `~/.opencode2-profiles/work/config/opencode/agent/` | node charters |
| `~/Desktop/Attri/nudge` | program compiler (`nudge` CLI, `.nudge.md` genotypes) |
| `~/Desktop/Attri/telepathy` | context layer, desk engine, agent map (source of charters) |

## Update flow

1. `oc2-update` (script, also exposed as the `oc2_update` tool):
   `git -C ~/opencode2 pull` → `bun install` → build → report revision.
2. Plugin set is versioned with the profile config; plugin changes ride the same
   pull when they live in `~/opencode2/specs/plugins-src/` and are synced out.
3. Changelog entry drafted at `~/.opencode2-profiles/CHANGELOG-DRAFTS/`.
4. Posting to buzz `changelog` happens only via `buzz` in the owner environment.

## Team loop (distribution)

1. Owner publishes: `oc2-team.sh publish` → labs serves `team.json`, the profile
   bundle, the scripts, and the prebuilt binary.
2. A teammate joins with one command: `curl -fsSL https://labs.intuitxn.com/join/oc2-join.sh | sh`
   — installs the build as `oc2` (their own `opencode` untouched), the canonical
   profile, agents + plugins, the resident node, and the gateway — all LaunchAgents.
3. Members auto-pull: `oc2-sync` (15 min) applies the bundle; the manifest's
   `access_tiers` decides what each tier gets. Owner pushes by publishing; nodes pull.
4. buzz identity is owner-admitted per member (Nest). Keys never leave machines.
5. Jobs from the relay or the gateway intake run sandboxed (seatbelt), or deeper
   (docker/lima) when the program needs an OS.

## Failures

- No provider connected → agents work, model calls fail loudly. Runtimes adapter
  still works for codex workers.
- Relay unreachable → network tools say so; plugins never fill gaps with assumed
  context.
- Build broken → wrapper keeps running the last good dist; update tool refuses
  to swap a binary that fails `--version`.
