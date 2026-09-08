import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"

const binary = `${process.env.HOME}/.local/bin/telepathy-program`
const names = ["artifact-design", "lesson-proposal", "lesson-review"] as const

async function invoke(args: string[], input = "") {
  if (!(await Bun.file(binary).exists())) return "telepathy-program is not installed on this node"
  const proc = Bun.spawn([binary, ...args], { stdin: "pipe", stdout: "pipe", stderr: "ignore" })
  proc.stdin.write(input)
  proc.stdin.end()
  const timer = setTimeout(() => proc.kill(), 150000)
  try {
    const output = await new Response(proc.stdout).text()
    const code = await proc.exited
    return JSON.stringify({ code, result: JSON.parse(output) })
  } finally {
    clearTimeout(timer)
  }
}

export const ProgramsPlugin: Plugin = async () => ({
  tool: {
    programs_list: tool({
      description: "List typed Nudge programs available to this node and their input/output contracts.",
      args: {},
      async execute() { return invoke(["list"]) },
    }),
    programs_compile: tool({
      description: "Compile an allowlisted Markdown program to an immutable Nudge bundle. Compilation is not execution or evaluation.",
      args: { program: tool.schema.enum(names) },
      async execute({ program }) { return invoke(["compile", program]) },
    }),
    programs_run: tool({
      description: "Execute one typed Nudge transaction through the local OpenCode wrapper. Inputs must match its schema. Returns validated output and receipt; never publishes, approves or promotes a change.",
      args: { program: tool.schema.enum(names), inputs: tool.schema.string().describe("JSON object matching the declared inputs") },
      async execute({ program, inputs }) {
        const value = JSON.parse(inputs)
        if (!value || Array.isArray(value) || typeof value !== "object") throw new Error("inputs must be a JSON object")
        if (inputs.length > 100000) throw new Error("inputs exceed program request limit")
        return invoke(["run", program], inputs)
      },
    }),
  },
})
