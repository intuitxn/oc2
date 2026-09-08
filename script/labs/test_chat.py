import tempfile
import unittest
from pathlib import Path
from server import Workspace

class Runtime:
    def __init__(self):
        self.rows=[dict(id='parent',running=True,status='idle',directory='/tmp',archived=False)]
        self.calls=[]
    def list(self):return self.rows
    def spawn(self,prompt,directory,parent='',group=''):
        self.calls.append((prompt,directory,parent,group))
        self.rows.append(dict(id='child',directory=directory,running=True,status='starting',archived=False))
        return {'id':'child'}
    def send(self,key,prompt):self.calls.append((key,prompt));return {'id':key,'status':'working'}

class ChatTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.runtime=Runtime()
        self.workspace=Workspace(str(Path(self.temp.name)/'state.sqlite'),self.runtime)
    def tearDown(self):self.temp.cleanup()
    def test_child_is_direct_opencode_with_parent_directory(self):
        result=self.workspace.chat('spawn',{'prompt':'Build UX','parent':'parent','group':'labs/design'})
        self.assertEqual(result['id'],'child')
        self.assertEqual(self.runtime.calls,[('Build UX','/tmp','parent','labs/design')])
        self.assertEqual(self.workspace.parents(),{'child':'parent'})
    def test_other_runtimes_and_invalid_inputs_rejected(self):
        for body in ({'prompt':'hello','tool':'codex'},{'prompt':''},{'prompt':'hello','group':'../bad'}):
            with self.assertRaises(ValueError):self.workspace.chat('spawn',body)
        self.assertEqual(self.runtime.calls,[])
    def test_messages_are_literal(self):
        value='Keep `this` and $(that) literal.'
        self.workspace.chat('send',{'session':'parent','prompt':value})
        self.assertEqual(self.runtime.calls,[('parent',value)])
