import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"

// buzz.ts — the network surface, draft-only. Reads relay state through the
// `buzz` CLI when present; every write this plugin produces is a draft file in
// the profile's outbox. Sending lives in the owner environment (buzz Desktop /
// BUZZ_PRIVATE_KEY env) — this plugin never reads, prints, or stores keys.

const OUTBOX = `${process.env.HOME}/.opencode2-profiles/work/OUTBOX`

export const BuzzPlugin: Plugin = async () => {
  return {
    tool: {
      buzz_channels_list: tool({
        description:
          "List buzz relay channels visible to the local buzz CLI. Reports unavailability honestly; never fills gaps with assumed context.",
        args: {},
        async execute() {
          if (!Bun.which("buzz")) return "buzz CLI not installed; relay state unavailable"
          const proc = Bun.spawn(["buzz", "channels", "list"], { stdout: "pipe", stderr: "pipe",
            env: { ...process.env, BUZZ_RELAY_URL: process.env.INTUITXN_NETWORK || process.env.BUZZ_RELAY_URL || "https://intuitxn.communities.buzz.xyz" },
          })
          const [out, err] = await Promise.all([new Response(proc.stdout).text(), new Response(proc.stderr).text()])
          const code = await proc.exited
          return code === 0 ? out : `buzz channels list failed (${code}):\n${err}`
        },
      }),
      buzz_draft: tool({
        description:
          "Write a draft post/reply/changelog entry to this node's outbox for human review. Drafts are files — they are never sent. The human sends from their buzz environment after review.",
        args: {
          kind: tool.schema.enum(["post", "reply", "changelog", "resolution"]).describe("Draft type"),
          channel: tool.schema.string().describe("Target channel name"),
          title: tool.schema.string().describe("Draft title (first line / changelog heading)"),
          body: tool.schema.string().describe("Full draft body. Answer: what changed, why it matters, what is needed."),
        },
        async execute({ kind, channel, title, body }) {
          const dir = `${OUTBOX}/${kind}`
          const file = `${dir}/${new Date().toISOString().slice(0, 16).replace("T", "-")}-${channel}.md`
          await Bun.write(
            file,
            `---\nkind: ${kind}\nchannel: ${channel}\ntitle: ${JSON.stringify(title)}\nstatus: draft\ncreated: ${new Date().toISOString()}\n---\n\n${body}\n`,
          )
          return `draft written: ${file}\nnext: human review -> send from owner buzz environment`
        },
      }),
    },
    async event({ event }) {
      // keep honest: log relay-facing tool failures to the session log only
      if (event.type === "tool.execute.error" || event.type === "permission.rejected") {
        await Bun.write(`${OUTBOX}/.events.log`, `${new Date().toISOString()} ${JSON.stringify(event)}\n`, { append: true })
      }
    },
  }
}
