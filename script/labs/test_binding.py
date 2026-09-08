import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from server import Workspace

class BindingTest(unittest.TestCase):
    def test_scoped_start_and_duplicate_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);repo=root/'repo';repo.mkdir()
            for args in (['init','-b','main'],['config','user.name','Test'],['config','user.email','test@example.test']):
                subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True)
            (repo/'note').write_text('base')
            for args in (['add','note'],['commit','-m','base']):subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True)
            cli=root/'manager';cli.write_text('''#!/usr/bin/env python3
import sys,json
from pathlib import Path
p=Path(__file__).with_name('calls.jsonl')
with p.open('a') as f:f.write(json.dumps(sys.argv[1:])+'\\n')
if sys.argv[1]=='groups': print('[]')
elif sys.argv[1]=='spawn': print('{"session":{"id":"testchild"}}')
else: print('{}')
''');cli.chmod(0o700)
            host=Workspace(str(root/'state.sqlite'),str(cli))
            work=host.ops.create({'repo':str(repo),'objective':'Scoped test','acceptance':'Only note','scope':['note'],'checks':[]})
            started=host.operation(work['id'],'start',{'tool':'codex'})
            self.assertEqual(started['id'],'testchild')
            calls=[json.loads(line) for line in (root/'calls.jsonl').read_text().splitlines()]
            spawn=next(call for call in calls if call[0]=='spawn')
            self.assertEqual(spawn[spawn.index('--directory')+1],work['worktree'])
            self.assertEqual(host.detail(work['id'])['binding']['session'],'testchild')
            with self.assertRaises(ValueError):host.operation(work['id'],'start',{'tool':'codex'})
            self.assertEqual(sum(json.loads(line)[0]=='spawn' for line in (root/'calls.jsonl').read_text().splitlines()),1)
