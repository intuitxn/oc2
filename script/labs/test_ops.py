import pathlib
import subprocess
import sys
import tempfile
import unittest
from ops import Ops

class Operations(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@localhost')
        (self.repo / 'a.txt').write_text('base\n')
        (self.repo / 'outside').write_text('original\n')
        self.git('add', '.')
        self.git('commit', '-m', 'base')
        self.ops = Ops(self.root / 'state' / 'db.sqlite')

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.DEVNULL, text=True).strip()

    def create(self, **args):
        body = dict(repo=str(self.repo), objective='Edit a', acceptance='a changes', scope=['a.txt'],
                    checks=[[sys.executable, '-c', 'from pathlib import Path; assert Path("a.txt").exists()']])
        body.update(args)
        return self.ops.create(body)

    def candidate(self):
        op = self.create()
        (pathlib.Path(op['worktree']) / 'a.txt').write_text('candidate\n')
        return self.ops.action(op['id'], 'snapshot')

    def test_full_review_merge(self):
        op = self.candidate()
        op = self.ops.action(op['id'], 'verify')
        self.assertEqual(op['status'], 'verified')
        with self.assertRaises(ValueError):
            self.ops.action(op['id'], 'land', {'digest': op['review']['digest']})
        self.ops.action(op['id'], 'approve', {'digest': op['review']['digest']})
        op = self.ops.action(op['id'], 'land', {'digest': op['review']['digest']})
        self.assertEqual(op['status'], 'landed')
        self.assertEqual((self.repo / 'a.txt').read_text(), 'candidate\n')
        self.assertEqual(self.git('rev-parse', 'HEAD'), op['review']['integration'])
        with self.assertRaises(ValueError):
            self.ops.action(op['id'], 'checkpoint', {'text':'changed'})

    def test_scope_and_symlink(self):
        op = self.create()
        tree = pathlib.Path(op['worktree'])
        (tree / 'evil').write_text('no')
        with self.assertRaisesRegex(ValueError, 'outside scope'):
            self.ops.action(op['id'], 'snapshot')
        (tree / 'evil').unlink()
        (tree / 'a.txt').unlink()
        (tree / 'a.txt').symlink_to('/etc/passwd')
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            self.ops.action(op['id'], 'snapshot')

    def test_staged_hidden_change(self):
        op = self.create()
        tree = pathlib.Path(op['worktree'])
        (tree / 'outside').write_text('evil\n')
        self.ops.git(tree, 'add', 'outside')
        (tree / 'outside').write_text('original\n')
        with self.assertRaisesRegex(ValueError, 'outside scope'):
            self.ops.action(op['id'], 'snapshot')

    def test_stale_target_and_candidate(self):
        op = self.candidate()
        op = self.ops.action(op['id'], 'verify')
        self.ops.action(op['id'], 'approve', {'digest': op['review']['digest']})
        (self.repo / 'other').write_text('change')
        self.git('add', '.')
        self.git('commit', '-m', 'advance')
        with self.assertRaisesRegex(ValueError, 'Target changed'):
            self.ops.action(op['id'], 'land', {'digest': op['review']['digest']})
        (pathlib.Path(op['worktree']) / 'a.txt').write_text('new candidate')
        with self.assertRaisesRegex(ValueError, 'Candidate changed'):
            self.ops.action(op['id'], 'verify')

    def test_conflict_resolution(self):
        op = self.candidate()
        (self.repo / 'a.txt').write_text('target\n')
        self.git('add', '.')
        self.git('commit', '-m', 'diverge')
        op = self.ops.action(op['id'], 'verify')
        self.assertEqual(op['status'], 'conflict')
        with self.assertRaisesRegex(ValueError, 'Resolve'):
            self.ops.action(op['id'], 'repair')
        tree = pathlib.Path(op['integration_worktree'])
        (tree / 'a.txt').write_text('resolved\n')
        self.ops.git(tree, 'add', 'a.txt')
        op = self.ops.action(op['id'], 'repair')
        self.assertEqual(op['status'], 'verified')
        self.ops.action(op['id'], 'approve', {'digest': op['review']['digest']})
        self.ops.action(op['id'], 'land', {'digest': op['review']['digest']})
        self.assertEqual((self.repo / 'a.txt').read_text(), 'resolved\n')

    def test_context_and_fork(self):
        op = self.candidate()
        op = self.ops.action(op['id'], 'checkpoint', {'context': 'Selected decision only'})
        child = self.ops.action(op['id'], 'fork', {'context': 'Child context'})
        self.assertEqual(child['base'], op['candidate'])
        self.assertEqual(child['parent'], op['id'])
        self.assertEqual(child['context'], 'Child context')
        export = self.ops.action(op['id'], 'export')
        self.assertNotIn('repo', export)
        self.assertNotIn('worktree', export)
        self.assertEqual(export['context'], 'Selected decision only')

    def test_merge_selected_context(self):
        op = self.candidate()
        self.ops.action(op['id'], 'checkpoint', {'text': 'Parent decision'})
        child = self.ops.action(op['id'], 'fork', {'context': 'Private investigation details'})
        op = self.ops.action(op['id'], 'verify')
        self.ops.action(op['id'], 'approve', {'digest': op['review']['digest']})
        op = self.ops.action(op['id'], 'merge-context', {'source': child['id'], 'text': 'Accepted outcome'})
        self.assertIn('Parent decision', op['context'])
        self.assertIn('Accepted outcome', op['context'])
        self.assertNotIn('Private investigation details', op['context'])
        self.assertEqual(op['checkpoints'][-1]['provenance']['source'], child['id'])
        self.assertEqual(len(op['checkpoints'][-1]['provenance']['checkpoint']), 64)
        self.assertIsNone(op['review'])
        self.assertIsNone(op['approved'])
        with self.assertRaises(ValueError):
            self.ops.action(op['id'], 'merge-context', {'source': op['id'], 'text': 'self'})
        with self.assertRaises(ValueError):
            self.ops.action(op['id'], 'merge-context', {'source': child['id'], 'text': ''})

    def test_checks_failure_and_mutation(self):
        for command in ['raise SystemExit(3)', 'from pathlib import Path; Path("a.txt").write_text("dirty")']:
            op = self.create(checks=[[sys.executable, '-c', command]])
            self.ops.action(op['id'], 'snapshot')
            op = self.ops.action(op['id'], 'verify')
            self.assertEqual(op['status'], 'failed')
            with self.assertRaises(ValueError):
                self.ops.action(op['id'], 'approve', {'digest': op['review']['digest']})

    def test_review_invalidated_by_context_and_target(self):
        op = self.candidate()
        op = self.ops.action(op['id'], 'verify')
        digest = op['review']['digest']
        self.ops.action(op['id'], 'checkpoint', {'text': 'new decision'})
        with self.assertRaises(ValueError):
            self.ops.action(op['id'], 'approve', {'digest': digest})
        op = self.ops.action(op['id'], 'verify')
        (self.repo / 'other').write_text('advance')
        self.git('add', '.')
        self.git('commit', '-m', 'advance')
        with self.assertRaisesRegex(ValueError, 'Target changed'):
            self.ops.action(op['id'], 'approve', {'digest': op['review']['digest']})
        self.assertIsNone(self.ops.get(op['id'])['review'])

    def test_check_cannot_replace_integration_commit(self):
        op = self.create(checks=[['git', '-c', 'user.name=Test', '-c', 'user.email=test@local',
                                 'commit', '--allow-empty', '-m', 'unexpected']])
        self.ops.action(op['id'], 'snapshot')
        op = self.ops.action(op['id'], 'verify')
        self.assertEqual(op['status'], 'failed')

    def test_no_checks_and_dirty_owner(self):
        op = self.create(checks=[])
        self.ops.action(op['id'], 'snapshot')
        op = self.ops.action(op['id'], 'verify')
        self.assertEqual(op['status'], 'failed')
        op = self.candidate()
        op = self.ops.action(op['id'], 'verify')
        self.ops.action(op['id'], 'approve', {'digest': op['review']['digest']})
        (self.repo / 'local').write_text('uncommitted')
        with self.assertRaisesRegex(ValueError, 'clean'):
            self.ops.action(op['id'], 'land', {'digest': op['review']['digest']})

if __name__ == '__main__':
    unittest.main()
