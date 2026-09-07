import { sql } from "drizzle-orm"
import { Database } from "@/storage/db"
import { Log } from "@/util/log"

// Lamport clock — event-based logical ordering for the sync layer.
//
// One logical counter, persisted next to the event log. Every local event
// ticks it. Remote events (replay from another node) merge: max+1. Events
// are stamped with the clock at emission, so the event log, the gateway, and
// LAN nodes can order and merge without wall clocks.
//
// Persistence: a one-row table created on demand. No drizzle migration —
// the clock is infrastructure, not domain schema.

const log = Log.create({ service: "lamport" })

export namespace Lamport {
  let cached: number | undefined

  function ensure(db: Parameters<Parameters<typeof Database.use>[0]>[0]): any {
    const anyDb = db as any
    anyDb.run(
      sql`CREATE TABLE IF NOT EXISTS lamport_clock (id integer PRIMARY KEY CHECK (id = 1), value integer NOT NULL)`,
    )
    return anyDb
  }

  function load(): number {
    if (cached != null) return cached
    const row = Database.use((db) => {
      const d = ensure(db)
      return d.get(sql`SELECT value FROM lamport_clock WHERE id = 1`)
    }) as { value: number } | undefined
    cached = typeof row?.value === "number" ? row.value : 0
    return cached
  }

  function store(value: number) {
    Database.use((db) => {
      const d = ensure(db)
      d.run(sql`INSERT INTO lamport_clock (id, value) VALUES (1, ${value}) ON CONFLICT(id) DO UPDATE SET value = ${value}`)
    })
    cached = value
  }

  /** Read the current clock without ticking. */
  export function now(): number {
    return load()
  }

  /** Tick for a local event: clock+1, persisted. */
  export function tick(): number {
    const next = load() + 1
    store(next)
    log.debug("tick", { clock: next })
    return next
  }

  /** Merge a remote clock (replay from another node): max+1, persisted. */
  export function merge(remote: number): number {
    const next = Math.max(load(), Number(remote) || 0) + 1
    store(next)
    log.debug("merge", { remote, clock: next })
    return next
  }
}
