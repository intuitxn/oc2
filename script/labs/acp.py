"""Durable local sessions backed directly by OpenCode ACP, without a manager daemon."""
import json
import os
from pathlib import Path
import sqlite3
import signal
import subprocess
import threading
import time
import uuid


class RPC:
    def __init__(self, directory, callback, command=None):
        env = {key: value for key, value in os.environ.items() if key in (
            'HOME', 'PATH', 'USER', 'TMPDIR', 'SHELL', 'LANG', 'OC2_PROFILE', 'INTUITXN_NETWORK')}
        env['OPENCODE_CONFIG_CONTENT'] = json.dumps({'permission': 'ask'})
        self.process = subprocess.Popen(command or [str(Path.home() / '.local/bin/opencode'), 'acp', '--cwd', directory],
            cwd=directory, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1, start_new_session=True)
        self.callback = callback
        self.lock = threading.RLock()
        self.pending = {}
        self.counter = 0
        self.closed = False
        self.thread = threading.Thread(target=self.reader, daemon=True)
        self.thread.start()

    def write(self, message):
        with self.lock:
            if self.closed:
                raise ValueError('ACP process disconnected; resume the session')
            self.process.stdin.write(json.dumps(dict(jsonrpc='2.0', **message)) + '\n')
            self.process.stdin.flush()

    def call(self, method, params, timeout=60):
        with self.lock:
            self.counter += 1
            id = self.counter
            box = {'event': threading.Event()}
            self.pending[id] = box
            self.write(dict(id=id, method=method, params=params))
        if not box['event'].wait(timeout):
            with self.lock:
                self.pending.pop(id, None)
            raise ValueError('ACP request timed out: ' + method)
        if 'error' in box:
            # Provider messages may contain environment or credentials; keep raw errors out of logs/UI.
            raise ValueError('ACP request failed: ' + method)
        return box.get('result', {})

    def reader(self):
        try:
            for line in self.process.stdout:
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(message, dict):
                    continue
                if 'method' in message:
                    self.callback(message)
                    continue
                with self.lock:
                    box = self.pending.pop(message.get('id'), None)
                if box:
                    box.update(message)
                    box['event'].set()
        finally:
            with self.lock:
                self.closed = True
                for box in self.pending.values():
                    box['error'] = 'disconnected'
                    box['event'].set()
                self.pending.clear()
            self.callback({'method': 'labs/disconnected', 'params': {}})

    def close(self):
        try:
            os.killpg(self.process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.process.wait(timeout=3)


class ACP:
    def __init__(self, path, command=None):
        self.command = command
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.clients = {}
        self.replaying = set()
        self.stopped = set()
        self.active = set()
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS acp_sessions (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS acp_events (seq INTEGER PRIMARY KEY AUTOINCREMENT, session TEXT NOT NULL, data TEXT NOT NULL)')
            for id, data in db.execute('SELECT id,data FROM acp_sessions').fetchall():
                session = json.loads(data)
                if session['status'] in ('starting', 'working', 'permission', 'resuming'):
                    session.update(status='interrupted', permissions=[], error='Service restarted; resume explicitly. No prompt was repeated.')
                    db.execute('UPDATE acp_sessions SET data=? WHERE id=?', (json.dumps(session), id))

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def save(self, session):
        session['updated'] = time.time()
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO acp_sessions VALUES (?,?)', (session['id'], json.dumps(session)))
        return session

    def session(self, id):
        with self.connect() as db:
            row = db.execute('SELECT data FROM acp_sessions WHERE id=?', (id,)).fetchone()
        if not row:
            raise ValueError('Unknown ACP session')
        return json.loads(row[0])

    def event(self, id, data):
        with self.connect() as db:
            db.execute('INSERT INTO acp_events(session,data) VALUES (?,?)', (id, json.dumps(data)))

    def list(self):
        with self.connect() as db:
            return [self.project(json.loads(row[0])) for row in db.execute('SELECT data FROM acp_sessions ORDER BY rowid DESC')]

    def project(self, session):
        return dict(session, name=session.get('title', 'OpenCode session'), tool='opencode', busy=session['id'] in self.active,
                    running=session['status'] in ('idle', 'working', 'permission', 'starting', 'resuming'),
                    archived=False, **{'self': False})

    def read(self, id):
        session = self.session(id)
        with self.connect() as db:
            events = [dict(seq=row[0], **json.loads(row[1])) for row in db.execute(
                'SELECT seq,data FROM acp_events WHERE session=? ORDER BY seq DESC LIMIT 1000', (id,))][::-1]
        chunks = []
        for event in events:
            if event.get('type') == 'user':
                chunks.append('\n\nYou: ' + event.get('text', '') + '\n\nOpenCode: ')
            elif event.get('type') == 'agent':
                chunks.append(event.get('text', ''))
            elif event.get('type') == 'tool':
                update = event.get('update', {})
                chunks.append('\n[Tool: ' + str(update.get('title', update.get('toolCallId', 'operation'))) + ' · ' + str(update.get('status', update.get('sessionUpdate', ''))) + ']\n')
        if session.get('error'):
            chunks.append('\n\n' + session['error'])
        output = ''.join(chunks).strip()
        return dict(session=self.project(session), output=output, events=events, permissions=session.get('permissions', []))

    def spawn(self, prompt, directory, parent='', group=''):
        if not isinstance(directory, str) or not Path(directory).is_absolute() or not Path(directory).is_dir():
            raise ValueError('Session directory must be an existing absolute directory')
        self.prompt(prompt)
        if parent:
            self.session(parent)
        id = uuid.uuid4().hex
        with self.lock:
            self.save(dict(id=id, acp_id=None, directory=str(Path(directory).resolve()), parent=parent,
                           group=group, status='starting', permissions=[], created=time.time(), error=None,
                           model='opencode-go/deepseek-v4-flash', title=prompt[:100]))
            self.event(id, dict(type='user', text=prompt, at=time.time()))
            self.active.add(id)
            threading.Thread(target=self.work, args=(id, prompt), daemon=True).start()
        return {'id': id}

    def prompt(self, prompt):
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 200000:
            raise ValueError('Prompt must be nonempty text, at most 200000 characters')

    def callback(self, id, message):
        with self.lock:
            session = self.session(id)
            method = message['method']
            params = message.get('params', {})
            if method == 'labs/disconnected':
                if session['status'] in ('starting', 'working', 'permission', 'resuming'):
                    session.update(status='interrupted', permissions=[], error='ACP disconnected. Resume explicitly.')
                    self.save(session)
                return
            if method == 'session/request_permission':
                permission = dict(request=message['id'], tool=params.get('toolCall', {}), options=params.get('options', []))
                session['permissions'].append(permission)
                session['status'] = 'permission'
                self.save(session)
                return
            if 'id' in message:
                client = self.clients.get(id)
                if client:
                    client.write(dict(id=message['id'], error=dict(code=-32601, message='Client capability unavailable')))
                return
            if method == 'session/update' and id not in self.replaying:
                update = params.get('update', {})
                kind = update.get('sessionUpdate')
                if kind == 'agent_message_chunk':
                    content = update.get('content', {})
                    if content.get('type') == 'text':
                        self.event(id, dict(type='agent', text=content.get('text', ''), at=time.time()))
                elif kind in ('tool_call', 'tool_call_update'):
                    self.event(id, dict(type='tool', update=update, at=time.time()))

    def client(self, id):
        with self.lock:
            existing = self.clients.get(id)
            if existing and not existing.closed:
                return existing
            session = self.session(id)
            client = RPC(session['directory'], lambda message: self.callback(id, message), command=self.command)
            self.clients[id] = client
        init = client.call('initialize', dict(protocolVersion=1,
            clientCapabilities=dict(fs=dict(readTextFile=False, writeTextFile=False), terminal=False),
            clientInfo=dict(name='Intuitxn Labs', version='1')))
        if init.get('protocolVersion') != 1:
            raise ValueError('Unsupported ACP protocol version')
        params = dict(cwd=session['directory'], mcpServers=[])
        if session.get('acp_id'):
            if not init.get('agentCapabilities', {}).get('loadSession'):
                raise ValueError('ACP runtime does not support session loading')
            params['sessionId'] = session['acp_id']
            self.replaying.add(id)
            try:
                client.call('session/load', params)
            finally:
                self.replaying.discard(id)
        else:
            response = client.call('session/new', params)
            with self.lock:
                session = self.session(id)
                session['acp_id'] = response['sessionId']
                self.save(session)
        client.call('session/set_model', dict(sessionId=session['acp_id'], modelId=session['model']))
        return client

    def work(self, id, prompt=None):
        try:
            client = self.client(id)
            with self.lock:
                session = self.session(id)
                if id in self.stopped:
                    session.update(status='cancelled', permissions=[])
                    self.save(session)
                    return
                session.update(status='working' if prompt else 'idle', error=None)
                self.save(session)
            if prompt:
                result = client.call('session/prompt', dict(sessionId=session['acp_id'], prompt=[dict(type='text', text=prompt)]), timeout=3600)
                with self.lock:
                    session = self.session(id)
                    session.update(status='cancelled' if id in self.stopped else 'idle', stop_reason=result.get('stopReason'), permissions=[])
                    self.save(session)
        except Exception:
            with self.lock:
                session = self.session(id)
                session.update(status='cancelled' if id in self.stopped else 'error', permissions=[],
                               error='ACP operation failed. Check the local OpenCode runtime and authentication, then resume explicitly.')
                self.save(session)
            client = self.clients.get(id)
            if client:
                client.close()
        finally:
            with self.lock:
                self.active.discard(id)

    def send(self, id, prompt):
        self.prompt(prompt)
        with self.lock:
            session = self.session(id)
            if id in self.active or session['status'] in ('starting', 'working', 'permission', 'resuming'):
                raise ValueError('Session is busy; cancel or finish the current turn')
            self.stopped.discard(id)
            session.update(status='working', error=None)
            self.save(session)
            self.event(id, dict(type='user', text=prompt, at=time.time()))
            self.active.add(id)
            threading.Thread(target=self.work, args=(id, prompt), daemon=True).start()
        return dict(id=id, status='working')

    def resume(self, id):
        with self.lock:
            session = self.session(id)
            if id in self.active or session['status'] in ('starting', 'working', 'permission', 'resuming'):
                raise ValueError('Session is busy')
            self.stopped.discard(id)
            session.update(status='resuming', error=None)
            self.save(session)
            self.active.add(id)
            threading.Thread(target=self.work, args=(id,), daemon=True).start()
        return dict(id=id, status='resuming')

    def cancel(self, id):
        with self.lock:
            session = self.session(id)
            self.stopped.add(id)
            client = self.clients.get(id)
            if client and not client.closed:
                for permission in session.get('permissions', []):
                    client.write(dict(id=permission['request'], result=dict(outcome=dict(outcome='cancelled'))))
                if session.get('acp_id'):
                    client.write(dict(method='session/cancel', params=dict(sessionId=session['acp_id'])))
            session.update(status='cancelled', permissions=[])
            self.save(session)
        return dict(id=id, status='cancelled')

    def permission(self, id, request, option):
        with self.lock:
            session = self.session(id)
            permission = next((item for item in session['permissions'] if str(item['request']) == str(request)), None)
            if not permission or option not in [item['optionId'] for item in permission['options']]:
                raise ValueError('Unknown permission request or option')
            client = self.clients.get(id)
            if not client or client.closed:
                raise ValueError('Permission belongs to a disconnected ACP session')
            client.write(dict(id=permission['request'], result=dict(outcome=dict(outcome='selected', optionId=option))))
            session['permissions'].remove(permission)
            session['status'] = 'permission' if session['permissions'] else 'working'
            self.save(session)
        return dict(id=id, status=session['status'])

    def close(self):
        for client in list(self.clients.values()):
            client.close()
