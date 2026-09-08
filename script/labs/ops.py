"""Local scoped work operations. Scope validates Git candidates; it is not a sandbox."""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import subprocess
import time
import uuid


class Ops:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.root = self.path.parent / 'ops-worktrees'
        self.root.mkdir(exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS scoped_ops (id TEXT PRIMARY KEY, data TEXT NOT NULL)')

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    @contextlib.contextmanager
    def lock(self):
        with open(str(self.path) + '.ops.lock', 'a') as file:
            fcntl.flock(file, fcntl.LOCK_EX)
            yield

    def git(self, repo, *args, check=True):
        result = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false',
                                 '-c', 'user.name=Labs Work', '-c', 'user.email=labs@localhost',
                                 '-C', str(repo), *args], capture_output=True, text=True, timeout=60)
        if check and result.returncode:
            raise ValueError((result.stderr or result.stdout).strip()[:4000])
        return result

    def save(self, op):
        op['updated'] = time.time()
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO scoped_ops VALUES (?, ?)', (op['id'], json.dumps(op)))
        return op

    def list(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT data FROM scoped_ops ORDER BY rowid DESC')]

    def get(self, id):
        with self.connect() as db:
            row = db.execute('SELECT data FROM scoped_ops WHERE id=?', (id,)).fetchone()
        if not row:
            raise ValueError('Unknown work item')
        op = json.loads(row[0])
        if op.get('candidate'):
            op['diff'] = self.git(op['worktree'], 'diff', '--no-ext-diff', '--no-textconv', op['base'], op['candidate'], '--').stdout[:100000]
        if op.get('review'):
            op['integration_diff'] = self.git(op['integration_worktree'], 'diff', '--no-ext-diff', '--no-textconv', op['review']['target'], op['review']['integration'], '--').stdout[:100000]
        return op

    def create(self, body):
        with self.lock():
            return self.create_locked(body)

    def create_locked(self, body):
        if not isinstance(body, dict):
            raise ValueError('Work specification must be an object')
        context = self.context(body.get('context', ''))
        repo = Path(body.get('repo', ''))
        if not repo.is_absolute():
            raise ValueError('Repository must be an absolute path')
        repo = Path(self.git(repo, 'rev-parse', '--show-toplevel').stdout.strip()).resolve()
        scope = body.get('scope', [])
        if not isinstance(scope, list) or not scope:
            raise ValueError('At least one explicit scope path is required')
        for path in scope:
            self.pathcheck(path)
        checks = body.get('checks', [])
        if not isinstance(checks, list) or any(not isinstance(argv, list) or not argv or
                any(not isinstance(arg, str) or '\0' in arg for arg in argv) for argv in checks):
            raise ValueError('Checks must be a list of nonempty argv lists')
        objective = body.get('objective', '')
        if not isinstance(objective, str) or not objective.strip() or not body.get('acceptance'):
            raise ValueError('Objective and acceptance criteria are required')
        target = body.get('target') or self.git(repo, 'symbolic-ref', '--short', 'HEAD').stdout.strip()
        self.git(repo, 'check-ref-format', '--branch', target)
        base = self.git(repo, 'rev-parse', '--verify', 'refs/heads/' + target).stdout.strip()
        parent = body.get('parent')
        if parent:
            source = self.get(parent)
            if source['repo'] != str(repo):
                raise ValueError('Fork must use its parent repository')
            base = source.get('candidate') or source['base']
        id = uuid.uuid4().hex[:16]
        worktree = self.root / id
        branch = 'labs/work/' + id
        self.git(repo, 'worktree', 'add', '-b', branch, str(worktree), base)
        return self.save(dict(id=id, repo=str(repo), target=target, base=base, branch=branch,
                    worktree=str(worktree), parent=parent, objective=objective, acceptance=body['acceptance'],
                    scope=[path.rstrip('/') for path in scope], checks=checks,
                    context=context, checkpoints=[], status='working',
                    candidate=None, review=None, approved=None, created=time.time()))

    def context(self, text):
        if not isinstance(text, str) or len(text) > 200000:
            raise ValueError('Selected context must be text, at most 200000 characters')
        return text

    def pathcheck(self, path):
        if not isinstance(path, str) or not path or path.startswith(('/', '-', ':')) or '\\' in path or '\0' in path:
            raise ValueError('Scope paths must be plain relative paths')
        if any(part in ('..', '.', '.git') for part in path.split('/')):
            raise ValueError('Unsafe scope path')

    def scoped(self, op, tree, names):
        for name in names:
            self.pathcheck(name)
            if not any(name == path or name.startswith(path + '/') for path in op['scope']):
                raise ValueError('Change outside scope: ' + name)
            path = Path(tree) / name
            for part in [path, *path.parents]:
                if part == Path(tree):
                    break
                if part.is_symlink():
                    raise ValueError('Symlinks are not allowed in candidates: ' + name)
        # Reject committed symlinks/submodules even if their working paths were removed.
        for line in self.git(tree, 'ls-files', '--stage', '-z').stdout.split('\0'):
            if line.startswith(('120000 ', '160000 ')) and line.split('\t', 1)[-1] in names:
                raise ValueError('Symlink/submodule candidates are unsupported')

    def changes(self, tree, *refs):
        return set(filter(None, self.git(tree, 'diff', '--no-renames', '--name-only', '-z', *refs, '--').stdout.split('\0')))

    def clean(self, tree):
        return not self.git(tree, 'status', '--porcelain', '--untracked-files=all').stdout

    def exact(self, op):
        if not op.get('candidate'):
            raise ValueError('Snapshot a candidate first')
        if self.git(op['worktree'], 'rev-parse', 'HEAD').stdout.strip() != op['candidate'] or not self.clean(op['worktree']):
            raise ValueError('Candidate changed; snapshot and verify again')
        self.scoped(op, op['worktree'], self.changes(op['worktree'], op['base'], op['candidate']))

    def action(self, id, action, body=None):
        try:
            return self.dispatch(id, action, body)
        except ValueError as err:
            with self.lock():
                op = self.get(id)
                op['error'] = str(err)
                if 'changed;' in str(err):
                    op.update(review=None, approved=None, status='candidate')
                self.save(op)
            raise

    def dispatch(self, id, action, body=None):
        body = {} if body is None else body
        if not isinstance(body, dict):
            raise ValueError('Operation input must be an object')
        with self.lock():
            op = self.get(id)
            if action == 'export':
                return dict(schema='labs.work-context/v1', objective=op['objective'], acceptance=op['acceptance'],
                            scope=op['scope'], context=op['context'], base=op['base'], candidate=op['candidate'],
                            parent=op['parent'], source=op['id'])
            if op['status'] == 'landed' and action not in ('fork',):
                raise ValueError('Landed work is immutable; fork a new work item')
            if action == 'merge-context':
                source = body.get('source')
                if not isinstance(source, str) or source == id:
                    raise ValueError('Context source must be another work item')
                source = self.get(source)
                selected = self.context(body.get('text', ''))
                if not selected.strip():
                    raise ValueError('Select an accepted context summary to merge')
                provenance = dict(source=source['id'], candidate=source['candidate'],
                    checkpoint=hashlib.sha256(source['context'].encode()).hexdigest())
                op['context'] = self.context(op['context'] + '\n\nSelected accepted context from ' + source['id'] + ':\n' + selected)
                op['checkpoints'].append(dict(text=op['context'], selected=selected,
                    provenance=provenance, at=time.time(), candidate=op['candidate']))
                op.update(review=None, approved=None, status='candidate' if op['candidate'] else 'working')
                return self.save(op)
            if action == 'checkpoint':
                op['context'] = self.context(body.get('context', body.get('text', '')))
                op['checkpoints'].append(dict(text=op['context'], at=time.time(), candidate=op['candidate']))
                op.update(review=None, approved=None, status='candidate' if op['candidate'] else 'working')
                return self.save(op)
            if action == 'fork':
                return self.create_locked(dict(repo=op['repo'], target=op['target'], parent=id,
                    objective=body.get('objective') or op['objective'], acceptance=body.get('acceptance') or op['acceptance'],
                    scope=body.get('scope') or op['scope'], checks=body.get('checks', op['checks']),
                    context=body.get('context', op['context'])))
            if op['status'] == 'landed':
                raise ValueError('Landed work is immutable; fork a new work item')
            if action in ('snapshot', 'candidate'):
                tree = op['worktree']
                names = self.changes(tree, op['base']) | self.changes(tree, '--cached', op['base']) | set(filter(None,
                    self.git(tree, 'ls-files', '--others', '--exclude-standard', '-z').stdout.split('\0')))
                self.scoped(op, tree, names)
                if names:
                    self.git(tree, 'add', '--', *sorted(names))
                if self.git(tree, 'diff', '--cached', '--quiet', check=False).returncode:
                    self.git(tree, 'commit', '-m', 'Labs candidate: ' + op['objective'][:100])
                self.scoped(op, tree, self.changes(tree, op['base'], 'HEAD'))
                op.update(candidate=self.git(tree, 'rev-parse', 'HEAD').stdout.strip(), review=None,
                          approved=None, status='candidate', error=None)
                return self.save(op)
            if action == 'verify':
                self.exact(op)
                target = self.git(op['repo'], 'rev-parse', 'refs/heads/' + op['target']).stdout.strip()
                tree = self.root / (id + '-review-' + uuid.uuid4().hex[:8])
                self.git(op['repo'], 'worktree', 'add', '--detach', str(tree), target)
                op.update(integration_worktree=str(tree), review=None, approved=None, error=None)
                result = self.git(tree, 'merge', '--no-ff', '--no-commit', op['candidate'], check=False)
                if result.returncode:
                    op.update(status='conflict', error='Integration conflict. Resolve in the retained review worktree, then use repair.')
                    return self.save(op)
                return self.verify(op, tree, target)
            if action in ('repair', 'resolve'):
                self.exact(op)
                tree = op.get('integration_worktree')
                if op['status'] != 'conflict' or not tree:
                    raise ValueError('No conflicted integration to repair')
                if self.git(tree, 'diff', '--name-only', '--diff-filter=U').stdout:
                    raise ValueError('Resolve and stage all conflicts first')
                target = self.git(tree, 'rev-parse', 'HEAD').stdout.strip()
                if self.git(op['repo'], 'rev-parse', 'refs/heads/' + op['target']).stdout.strip() != target:
                    raise ValueError('Target changed; verify again')
                self.scoped(op, tree, self.changes(tree, target))
                return self.verify(op, tree, target)
            if action == 'approve':
                self.exact(op)
                if not op.get('review') or op['status'] != 'verified' or body.get('digest') != op['review']['digest']:
                    raise ValueError('Approval must match the verified review digest')
                if self.git(op['repo'], 'rev-parse', 'refs/heads/' + op['target']).stdout.strip() != op['review']['target']:
                    raise ValueError('Target changed; verify again')
                op.update(approved=body['digest'], status='approved')
                return self.save(op)
            if action in ('land', 'merge'):
                self.exact(op)
                review = op.get('review')
                if not review or op['status'] != 'approved' or body.get('digest') != op['approved'] or op['approved'] != review['digest']:
                    raise ValueError('Explicit approval of this exact review is required')
                repo = op['repo']
                if self.git(repo, 'rev-parse', 'refs/heads/' + op['target']).stdout.strip() != review['target']:
                    raise ValueError('Target changed; verify and approve again')
                if not self.clean(op['integration_worktree']) or self.git(op['integration_worktree'], 'rev-parse', 'HEAD').stdout.strip() != review['integration']:
                    raise ValueError('Integration changed; verify again')
                current = self.git(repo, 'symbolic-ref', '--short', 'HEAD', check=False).stdout.strip()
                if current != op['target'] or not self.clean(repo):
                    raise ValueError('Owning checkout must be clean and on the target branch')
                self.git(repo, 'merge', '--ff-only', review['integration'])
                op.update(status='landed', landed=review['integration'])
                return self.save(op)
            raise ValueError('Unknown work operation')

    def verify(self, op, tree, target):
        self.scoped(op, tree, self.changes(tree, target) | self.changes(tree, '--cached', target))
        if self.git(tree, 'rev-parse', '-q', '--verify', 'MERGE_HEAD', check=False).returncode == 0:
            self.git(tree, 'commit', '-m', 'Labs integration: ' + op['objective'][:100])
        expected = self.git(tree, 'rev-parse', 'HEAD').stdout.strip()
        if self.git(tree, 'merge-base', '--is-ancestor', op['candidate'], expected, check=False).returncode or self.git(tree, 'merge-base', '--is-ancestor', target, expected, check=False).returncode:
            raise ValueError('Integration must contain both exact target and candidate')
        parents = self.git(tree, 'show', '-s', '--format=%P', expected).stdout.strip().split()
        if expected != target and parents != [target, op['candidate']]:
            raise ValueError('Integration parent commits do not match this review')
        checks = []
        for argv in op['checks']:
            try:
                result = subprocess.run(argv, cwd=tree, capture_output=True, text=True, timeout=120)
                checks.append(dict(argv=argv, code=result.returncode, output=(result.stdout + result.stderr)[-12000:]))
            except (subprocess.TimeoutExpired, OSError) as err:
                checks.append(dict(argv=argv, code=-1, output=str(err)[:1000]))
        integration = self.git(tree, 'rev-parse', 'HEAD').stdout.strip()
        review = dict(candidate=op['candidate'], target=target, integration=integration, checks=checks,
                      context=op['context'], objective=op['objective'], acceptance=op['acceptance'], scope=op['scope'])
        review['digest'] = hashlib.sha256(json.dumps(review, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        op.update(review=review, approved=None, status='verified' if checks and all(check['code'] == 0 for check in checks) and self.clean(tree) and integration == expected else 'failed')
        if not checks:
            op['review']['notice'] = 'No automated checks configured; review only.'
        return self.save(op)
