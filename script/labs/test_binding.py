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
            from test_chat import Runtime
            runtime=Runtime()
            host=Workspace(str(root/'state.sqlite'),runtime)
            work=host.ops.create({'repo':str(repo),'objective':'Scoped test','acceptance':'Only note','scope':['note'],'checks':[]})
            started=host.operation(work['id'],'start',{'tool':'opencode'})
            self.assertEqual(started['id'],'child')
            self.assertEqual(runtime.calls[0][1],work['worktree'])
            self.assertEqual(host.detail(work['id'])['binding']['session'],'child')
            with self.assertRaises(ValueError):host.operation(work['id'],'start',{'tool':'opencode'})
            self.assertEqual(len(runtime.calls),1)
