"""CLI boundary checks never start or message real agents."""
import json
from pathlib import Path
import tempfile
import unittest
from server import Workspace

class ManagerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.log = self.root / 'argv.json'
        cli = self.root / 'manager'
        cli.write_text('''#!/usr/bin/env python3
import json,sys
from pathlib import Path
Path(__file__).with_name('argv.json').write_text(json.dumps(sys.argv[1:]))
if sys.argv[1]=='sessions':
 print(json.dumps([{'id':'parent','running':True,'directory':'/tmp','archived':False}, {'id':'dead','running':False,'archived':False}]))
elif sys.argv[1]=='spawn': print(json.dumps({'session':{'id':'child'}}))
elif sys.argv[1]=='send': print(json.dumps({'id':'message','status':'queued'}))
''')
        cli.chmod(0o700)
        self.workspace = Workspace(str(self.root / 'workspace.sqlite'), str(cli))
    def tearDown(self):
        self.temp.cleanup()
    def test_child_inherits_directory_and_persists_parent(self):
        result = self.workspace.manager('/api/manager/spawn', {'prompt':'Build UX','tool':'codex','parent':'parent','group':'labs/design'})
        self.assertEqual(result['id'], 'child')
        self.assertEqual(json.loads(self.log.read_text()), ['spawn','--prompt','Build UX','--tool','codex','--directory','/tmp','--group','labs/design','--json'])
        self.assertEqual(Workspace(self.workspace.path).parents(), {'child':'parent'})
    def test_reply_is_literal_and_returns_queue_receipt(self):
        prompt = 'Keep `this` and $(that) literal; do not execute.'
        result = self.workspace.manager('/api/manager/send', {'session':'parent','prompt':prompt})
        self.assertEqual(result['status'], 'queued')
        self.assertEqual(json.loads(self.log.read_text()), ['send','parent',prompt,'--json'])
    def test_invalid_actions_do_not_dispatch(self):
        for body in ({'prompt':'hi','tool':'unknown'}, {'prompt':'hi','group':'../bad'}, {'prompt':''}):
            with self.assertRaises(ValueError): self.workspace.manager('/api/manager/spawn', body)
        for key in ('missing','dead','../bad'):
            with self.assertRaises(ValueError): self.workspace.manager('/api/manager/send', {'session':key,'prompt':'hi'})
        self.assertNotIn('send', json.loads(self.log.read_text()))

if __name__ == '__main__': unittest.main()
