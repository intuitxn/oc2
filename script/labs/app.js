const $ = (id) => document.getElementById(id)
const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char])
let data = { sessions: [], parents: {} }
let selected = /^[a-zA-Z0-9_-]+$/.test(location.hash.slice(1)) && !['home', 'threads', 'agents', 'review'].includes(location.hash.slice(1)) ? location.hash.slice(1) : ''
let root = ''
let parent = ''
let creating = !selected
let archived = false
let busy = false
let version = 0
const folded = new Set()
const drafts = new Map()
const session = (id) => data.sessions.find((item) => item.id === id)
const active = (item) => !!item?.busy || ['starting', 'working', 'permission', 'resuming'].includes(item?.status)
async function api(path, body) {
  const response = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {})
  const result = await response.json()
  if (!response.ok) throw new Error(result.error || 'OpenCode ACP could not complete that action.')
  return result
}
function error(message = '') { $('error').textContent = message; $('error').hidden = !message }
function descendant(id, ancestor) {
  const seen = new Set()
  while (id && !seen.has(id)) {
    if (id === ancestor) return true
    seen.add(id)
    id = data.parents[id]
  }
  return false
}
function tree() {
  const query = $('search').value.toLowerCase()
  const sessions = data.sessions.filter((s) => !!s.archived === archived && (!root || descendant(s.id, root)))
  const matches = sessions.filter((s) => `${s.name} ${s.group} ${s.tool}`.toLowerCase().includes(query))
  const keys = new Set(matches.map((s) => s.id))
  const seen = new Set()
  const row = (s, level) => {
    if (seen.has(s.id)) return ''
    seen.add(s.id)
    const children = matches.filter((item) => data.parents[item.id] === s.id)
    const closed = folded.has('chat:' + s.id)
    const markup = `<button class="row ${escape(s.status)} ${s.id === selected && !creating ? 'selected' : ''}" data-session="${escape(s.id)}" aria-current="${s.id === selected && !creating ? 'true' : 'false'}"><span aria-hidden="true">${'│ '.repeat(level)}${children.length ? closed ? '▸' : '▾' : ' '}</span><span class="signal">${s.status === 'working' ? '●' : ['waiting', 'permission'].includes(s.status) ? '!' : s.status === 'dead' ? '×' : '·'}</span><span class="name">${escape(s.name || s.id)}</span><span class="state">${escape(s.status || 'unknown')}</span></button>`
    return markup + (closed && !query ? '' : children.map((child) => row(child, level + 1)).join(''))
  }
  const tops = matches.filter((s) => !keys.has(data.parents[s.id]) || s.id === root)
  const groups = new Map()
  for (const s of tops) {
    const path = s.group || ''
    if (!groups.has(path)) groups.set(path, [])
    groups.get(path).push(s)
  }
  const paths = new Set()
  for (const path of groups.keys()) {
    if (!path) continue
    const parts = path.split('/')
    parts.forEach((_, i) => paths.add(parts.slice(0, i + 1).join('/')))
  }
  const group = (path, level) => {
    const closed = folded.has('group:' + path)
    const members = matches.filter((s) => s.group === path || s.group?.startsWith(path + '/'))
    const waiting = members.filter((s) => s.status === 'waiting').length
    return `<button class="row group" data-group="${escape(path)}" aria-expanded="${!closed}"><span>${'│ '.repeat(level)}${closed ? '▸' : '▾'}</span><span class="name">${escape(path.split('/').pop())}/</span><small>${waiting ? waiting + ' waiting · ' : ''}${members.length}</small></button>` + (closed && !query ? '' : (groups.get(path) || []).map((s) => row(s, level + 1)).join('') + [...paths].filter((p) => p.slice(0, p.lastIndexOf('/')) === path && p.includes('/')).sort().map((p) => group(p, level + 1)).join(''))
  }
  const markup = (groups.get('') || []).map((s) => row(s, 0)).join('') + [...paths].filter((p) => !p.includes('/')).sort().map((p) => group(p, 0)).join('') || `<p class="no-results">${query ? 'No matching chats.' : data.error ? 'OpenCode ACP unavailable. Stored sessions remain available after reconnection.' : root ? 'No chats in this view.' : 'No chats here yet. Type a prompt below to start.'}</p>`
  if ($('tree').innerHTML !== markup) $('tree').innerHTML = markup
  $('scope').textContent = root ? 'root / ' + (session(root)?.name || root) : ''
  $('count').textContent = matches.length + ' chats' + (root ? ' in this root' : '')
  $('archived').classList.toggle('active', archived)
}
function remember() { drafts.set(creating ? 'new:' + parent : selected, $('prompt').value) }
function composer(s = session(selected)) {
  $('options').hidden = !creating
  $('target').textContent = creating ? 'new chat / ' + (session(parent)?.name || 'root') : 'reply / ' + (s?.name || selected)
  $('send').textContent = creating ? 'start ↵' : 'send ↵'
  $('hint').textContent = creating ? parent ? 'Fresh conversation under this chat. Uses its working directory.' : 'Starts a persistent OpenCode ACP session. Named from the work.' : 'Sent directly to the OpenCode ACP session.'
  $('prompt').placeholder = creating ? 'What should we work on?' : 'Reply to this chat…'
  $('send').disabled = busy || (!creating && (!s?.running || s?.archived || active(s)))
  $('prompt').disabled = !creating && (!s?.running || s?.archived)
}
function blank() {
  $('title').textContent = parent ? 'new chat / ' + session(parent)?.name : 'root / new chat'
  $('status').textContent = ''
  $('meta').textContent = parent ? 'parent ' + parent + ' · fresh conversation' : 'Any chat can be a root. Groups are paths, not separate products.'
  $('focus').hidden = true
  $('child').hidden = true
  $('session-cancel').hidden = true
  $('session-resume').hidden = true
  permissions = []; requests()
  $('conversation').innerHTML = '<div class="empty"><h1>One sentence.<br>Pick up the work.</h1><p>No setup ceremony. Type what you need below.<br>Names and groups keep the work navigable.</p><p class="keys">n new chat &nbsp; / find &nbsp; ↵ send</p></div>'
}
function create(id = '') {
  remember()
  ++version
  parent = id
  creating = true
  $('prompt').value = drafts.get('new:' + parent) || ''
  $('group').value = session(parent)?.group || ''
  $('receipt').textContent = ''
  blank(); composer(); tree()
  $('prompt').focus()
}
async function read() {
  if (creating || !selected) return
  const key = selected
  const revision = ++version
  const result = await api('/api/session/' + encodeURIComponent(key))
  if (revision !== version || creating || key !== selected) return
  const s = result.session || session(key)
  $('title').textContent = s?.name || key
  $('status').textContent = s?.status || 'unknown'
  $('status').className = s?.status || ''
  $('meta').textContent = [s?.tool, s?.group ? '/' + s.group : '/ root', s?.directory, key].filter(Boolean).join(' · ')
  const pane = $('conversation')
  const bottom = pane.scrollHeight - pane.scrollTop - pane.clientHeight < 60
  let pre = pane.querySelector('pre')
  if (!pre) { pane.replaceChildren(); pre = document.createElement('pre'); pane.append(pre) }
  const output = typeof result.output === 'string' ? result.output : 'No output yet.'
  if (pre.textContent !== output) pre.textContent = output
  if (bottom) pane.scrollTop = pane.scrollHeight
  $('focus').hidden = false
  $('child').hidden = false
  $('session-cancel').hidden = !active(s)
  $('session-cancel').disabled = !active(s)
  $('session-resume').hidden = active(s) || (!!s?.running && !['interrupted', 'error', 'errored', 'cancelled'].includes(s?.status))
  permissions = (result.permissions || []).map((request) => ({ ...request, id: request.id ?? request.request, toolCall: request.toolCall ?? request.tool })); requests()
  composer(s)
}
async function select(id) {
  remember()
  selected = id
  permissions = []; requests()
  creating = false
  parent = ''
  history.replaceState(null, '', '#' + encodeURIComponent(id))
  $('prompt').value = drafts.get(id) || ''
  $('receipt').textContent = ''
  $('title').textContent = session(id)?.name || id
  $('conversation').innerHTML = '<pre>Reading the agent…</pre>'
  tree(); composer()
  await read()
}
async function refresh() {
  data = await api('/api/workspace')
  error(data.error || '')
  $('connection').textContent = data.error ? 'disconnected' : '● local / live'
  $('summary').textContent = `OpenCode ACP / ${data.sessions.filter((s) => s.status === 'working').length} working · ${data.sessions.filter((s) => s.status === 'waiting').length} waiting`
  tree()
  if (!creating) await read()
}
$('tree').onclick = (event) => {
  const row = event.target.closest('button')
  if (!row) return
  if (row.dataset.session) select(row.dataset.session).catch((err) => error(err.message))
  if (row.dataset.group) {
    const key = 'group:' + row.dataset.group
    folded.has(key) ? folded.delete(key) : folded.add(key)
    tree()
  }
}
$('search').oninput = tree
$('new').onclick = () => create()
$('child').onclick = () => create(selected)
$('focus').onclick = () => { root = selected; tree() }
$('all').onclick = () => { root = ''; tree() }
$('home').onclick = (event) => { event.preventDefault(); root = ''; tree() }
$('archived').onclick = () => { archived = !archived; tree() }
$('refresh').onclick = () => refresh().catch((err) => error(err.message))
$('composer').onsubmit = async (event) => {
  event.preventDefault()
  if (busy || $('send').disabled) return
  const prompt = $('prompt').value.trim()
  if (!prompt) return
  const target = selected
  const draft = creating
  const owner = parent
  busy = true; composer(); error()
  try {
    const result = await api('/api/acp/' + (draft ? 'spawn' : 'send'), draft ? { prompt, tool: 'opencode', group: $('group').value, parent: owner } : { prompt, session: target })
    drafts.delete(draft ? 'new:' + owner : target)
    $('prompt').value = ''
    await refresh()
    if (draft && result.id) await select(result.id)
    $('receipt').textContent = draft ? 'OpenCode ACP session started.' : 'Message accepted by OpenCode ACP.'
  } catch (err) { error(err.message) } finally { busy = false; composer() }
}
$('prompt').onkeydown = (event) => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); $('composer').requestSubmit() }
}
document.onkeydown = (event) => {
  if (event.target.matches('input, textarea, select') || event.ctrlKey || event.metaKey || event.altKey) return
  if (event.key === 'n') { event.preventDefault(); create(); return }
  if (event.key === '/') { event.preventDefault(); $('search').focus(); return }
  if (event.key === ' ') { event.preventDefault(); $('prompt').focus(); return }
  if (event.key === 'Escape') { root = ''; tree(); return }
  const buttons = [...$('tree').querySelectorAll('button')]
  const index = buttons.indexOf(document.activeElement)
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault()
    buttons[Math.max(0, Math.min(buttons.length - 1, index + (event.key === 'ArrowDown' ? 1 : -1)))]?.focus()
  }
  if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
    const row = buttons[index]
    if (!row) return
    event.preventDefault()
    const key = row.dataset.group ? 'group:' + row.dataset.group : 'chat:' + row.dataset.session
    event.key === 'ArrowLeft' ? folded.add(key) : folded.delete(key)
    tree()
    const target = [...$('tree').querySelectorAll('button')].find((button) => button.dataset.group === row.dataset.group && button.dataset.session === row.dataset.session)
    target?.focus()
  }
}
async function poll() {
  try { if (!busy && !document.hidden) await refresh() } catch (err) { error(err.message); $('connection').textContent = 'disconnected' }
  setTimeout(poll, 4000)
}
refresh().then(() => { if (creating) blank(); composer(); setTimeout(poll, 4000) }).catch((err) => error(err.message))

// Work forms are kept outside the polled chat DOM so drafts survive refreshes.
let works = []
let work = null
let pending = false
const contexts = new Map()
function preserve() { if (work) contexts.set(work.id, { text: $('work-selected').value, objective: $('work-fork-objective').value, source: $('work-source').value }) }
function warning(message = '') { $('work-error').textContent = message; $('work-error').hidden = !message }
function listing() {
  const seen = new Set()
  const row = (item, depth) => {
    if (seen.has(item.id)) return ''
    seen.add(item.id)
    return `<button class="row ${work?.id === item.id ? 'selected' : ''}" data-work="${escape(item.id)}"><span>${'│ '.repeat(Math.min(depth, 12))}</span><span class="name">${escape(item.objective)}</span><small>${escape(item.status)}</small></button>` + works.filter((child) => child.parent === item.id).map((child) => row(child, depth + 1)).join('')
  }
  $('work-tree').innerHTML = works.filter((item) => !works.some((parent) => parent.id === item.parent)).map((item) => row(item, 0)).join('') + works.filter((item) => !seen.has(item.id)).map((item) => row(item, 0)).join('') || '<p class="no-results">No work branches yet.</p>'
}
function buttons() {
  $('work-controls').querySelectorAll('button').forEach((button) => { button.disabled = pending || !work })
  const digest = work?.review?.digest
  $('work-approve').disabled = pending || !digest || work?.status !== 'verified' || !$('work-reviewed').checked
  $('work-land').disabled = pending || !digest || work?.status !== 'approved'
  $('work-start').disabled = pending || !work || !!work?.binding
  $('work-resume').disabled = pending || !work?.binding?.session
  $('work-create').querySelector('button').disabled = pending
}
function detail() {
  $('work-create').hidden = !!work
  $('work-detail').hidden = !work
  $('work-controls').hidden = !work
  $('work-reviewed').checked = false
  if (!work) { buttons(); listing(); return }
  const field = (label, value) => `<dt>${escape(label)}</dt><dd>${escape(typeof value === 'string' ? value : JSON.stringify(value, null, 2))}</dd>`
  $('work-detail').innerHTML = `<h2>${escape(work.objective)}</h2><dl>${[['State', work.status], ['Repository', work.repo], ['Branch', work.branch], ['Target', work.target], ['Base', work.base], ['Candidate', work.candidate || 'No snapshot yet'], ['Worktree', work.worktree], ['Session', work.binding?.session || work.session || work.session_id || 'Not started'], ['Acceptance', work.acceptance], ['Allowed paths', work.scope], ['Review digest', work.review?.digest || 'Not verified'], ['Target at verification', work.review?.target || '—'], ['Integration', work.review?.integration || '—']].map(([label, value]) => field(label, value)).join('')}</dl>${work.error ? `<p class="work-failure">${escape(work.error)}</p>` : ''}<details open><summary>Selected context</summary><pre>${escape(work.context || 'No context checkpoint.')}</pre></details><details open><summary>Candidate diff · base → candidate</summary><pre>${escape(work.diff || work.review?.diff || 'No candidate diff.')}</pre></details><details open><summary>Integration diff · target → reviewed integration</summary><pre>${escape(work.integration_diff || 'No verified integration diff.')}</pre></details><details open><summary>Verification evidence</summary><pre>${escape(JSON.stringify(work.review || {}, null, 2))}</pre></details><details><summary>Recorded work state</summary><pre>${escape(JSON.stringify(work, null, 2))}</pre></details>`
  buttons(); listing()
}
async function catalog() {
  const result = await api('/api/ops')
  works = Array.isArray(result) ? result : result.ops || result.works || []
  listing()
}
async function choose(id) {
  preserve()
  const result = await api('/api/ops/' + encodeURIComponent(id))
  work = result.op || result.work || result
  $('work-selected').value = contexts.get(id)?.text || ''
  $('work-fork-objective').value = contexts.get(id)?.objective || ''
  $('work-source').value = contexts.get(id)?.source || ''
  warning(); detail()
}
$('work-toggle').onclick = async () => {
  const opened = $('work').hidden
  $('work').hidden = !opened
  $('work-toggle').setAttribute('aria-expanded', String(opened))
  for (const id of ['conversation', 'composer', 'meta', 'receipt', 'permissions']) $(id).hidden = opened
  if (!opened) { requests(); return }
  if (!$('work-repo').value) $('work-repo').value = session(selected)?.directory || ''
  try { await catalog() } catch (err) { warning(err.message) }
}
$('work-new').onclick = () => { if (pending) return; preserve(); work = null; warning(); detail(); $('work-objective').focus() }
$('work-refresh').onclick = async () => {
  if (pending) return
  try { await catalog(); if (work) { const result = await api('/api/ops/' + encodeURIComponent(work.id)); work = result.op || result.work || result; detail() } } catch (err) { warning(err.message) }
}
$('work-tree').onclick = (event) => {
  const id = event.target.closest('[data-work]')?.dataset.work
  if (id && !pending) choose(id).catch((err) => warning(err.message))
}
$('work-create').onsubmit = async (event) => {
  event.preventDefault()
  if (pending) return
  pending = true; warning(); buttons()
  try {
    const checks = JSON.parse($('work-checks').value)
    if (!Array.isArray(checks) || checks.some((argv) => !Array.isArray(argv) || !argv.length || argv.some((arg) => typeof arg !== 'string'))) throw new Error('Commands must be JSON arrays of string arguments, for example [["bun", "test"]].')
    const result = await api('/api/ops', { objective: $('work-objective').value, repo: $('work-repo').value, acceptance: $('work-acceptance').value, scope: $('work-scope').value.split('\n').map((path) => path.trim()).filter(Boolean), checks, context: $('work-context').value })
    work = result.op || result.work || result
    $('work-notice').textContent = 'Isolated work branch created.'
    await catalog(); detail()
  } catch (err) { warning(err.message) } finally { pending = false; buttons() }
}
$('work-reviewed').onchange = buttons
$('work-controls').onclick = async (event) => {
  const action = event.target.closest('[data-op]')?.dataset.op
  if (!action || !work || pending || event.target.closest('button').disabled) return
  preserve()
  const id = work.id
  const digest = work.review?.digest
  const context = $('work-selected').value.trim()
  if (['checkpoint', 'fork', 'merge-context'].includes(action) && !context) { warning('Select and enter the context to carry into this operation.'); return }
  if (action === 'fork' && !$('work-fork-objective').value.trim()) { warning('Give the fork a concrete objective.'); return }
  if (action === 'merge-context' && !$('work-source').value.trim()) { warning('Enter the source work ID for the accepted decisions.'); return }
  const payload = action === 'merge-context' ? { source: $('work-source').value.trim(), text: context } : action === 'checkpoint' ? { text: context } : action === 'fork' ? { context, objective: $('work-fork-objective').value.trim() } : action === 'link' ? { session: $('work-link').value.trim() } : action === 'start' ? { tool: 'opencode', parent: selected || '' } : ['approve', 'land'].includes(action) ? { digest } : {}
  pending = true; warning(); buttons()
  try {
    const result = await api('/api/ops/' + encodeURIComponent(id) + '/' + action, payload)
    if (action === 'export') {
      const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }))
      const link = document.createElement('a'); link.href = url; link.download = `work-${id}.json`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
    } else {
      const next = result.op || result.work || result
      const current = await api('/api/ops/' + encodeURIComponent(action === 'fork' ? next.id : id))
      work = current.op || current.work || current
      if (['checkpoint', 'fork', 'merge-context'].includes(action)) { contexts.delete(id); $('work-selected').value = ''; $('work-fork-objective').value = ''; $('work-source').value = '' }
      detail()
      if (action === 'start' || action === 'resume') { await refresh(); const sid = result.id || result.session?.id || result.session_id || work.session_id || work.session; if (typeof sid === 'string' && session(sid)) await select(sid) }
    }
    $('work-notice').textContent = action === 'approve' ? 'Exact candidate approved. Merge is a separate action.' : action === 'land' ? 'Approved integration merged.' : action + ' completed.'
    await catalog()
  } catch (err) {
    warning(err.message)
    try { const result = await api('/api/ops/' + encodeURIComponent(id)); work = result.op || result.work || result; detail() } catch { /* Keep the original operation error visible. */ }
  } finally { pending = false; buttons() }
}

let running = false
$('program-load').onclick = async () => {
  try {
    const result = await api('/api/programs')
    const programs = result.programs || []
    $('program-name').replaceChildren(...programs.map((item) => { const option = document.createElement('option'); option.value = item.name; option.textContent = item.name; return option }))
    $('program-output').textContent = JSON.stringify(result, null, 2)
  } catch (err) { warning(err.message) }
}
async function program(action) {
  if (running) return
  if (!$('program-name').value) { warning('Load the catalog and select a program first.'); return }
  running = true
  $('program-run').disabled = true; $('program-compile').disabled = true
  warning(); $('program-output').textContent = action === 'run' ? 'Running the typed program…' : 'Compiling…'
  try {
    const inputs = action === 'run' ? JSON.parse($('program-input').value) : {}
    if (!inputs || typeof inputs !== 'object' || Array.isArray(inputs)) throw new Error('Program inputs must be a JSON object.')
    const result = await api('/api/programs/' + encodeURIComponent($('program-name').value) + '/' + action, action === 'run' ? { inputs } : {})
    $('program-output').textContent = JSON.stringify(result, null, 2)
  } catch (err) { warning(err.message); $('program-output').textContent = 'The operation did not complete successfully.' } finally { running = false; $('program-run').disabled = false; $('program-compile').disabled = false }
}
$('program-compile').onclick = () => program('compile')
$('program-run').onclick = () => program('run')

let permissions = []
let rendered = null
const deciding = new Set()
function requests() {
  const pane = $('permissions')
  pane.hidden = !permissions.length || !$('work').hidden
  const markup = permissions.map((request, index) => `<div class="permission"><strong>Permission requested</strong><pre>${escape(request.toolCall?.title || request.title || 'The agent needs your decision to continue.')}</pre><details><summary>Request details</summary><pre>${escape(JSON.stringify(request.toolCall || request, null, 2))}</pre></details><div class="actions">${(request.options || []).map((option, choice) => `<button data-request="${index}" data-choice="${choice}" ${deciding.has(String(request.id)) ? 'disabled' : ''}>${escape(option.name || option.kind || option.optionId)}</button>`).join('')}</div></div>`).join('')
  if (rendered !== markup) { pane.innerHTML = markup; rendered = markup }
}
$('permissions').onclick = async (event) => {
  const button = event.target.closest('[data-request]')
  if (!button || button.disabled) return
  const request = permissions[Number(button.dataset.request)]
  const option = request?.options?.[Number(button.dataset.choice)]
  if (!request || !option) return
  const id = String(request.id)
  if (deciding.has(id)) return
  deciding.add(id); requests(); error()
  try {
    await api('/api/acp/permission', { session: selected, request: request.id, option: option.optionId })
    await read()
  } catch (err) { error(err.message) } finally { deciding.delete(id); requests() }
}
for (const action of ['cancel', 'resume']) $('session-' + action).onclick = async () => {
  const button = $('session-' + action)
  button.disabled = true; error()
  try { await api('/api/acp/' + action, { session: selected }); await refresh() } catch (err) { error(err.message) } finally { button.disabled = false }
}
