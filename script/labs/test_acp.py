"""Exercise the actual stdio transport against a deterministic ACP peer."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from acp import ACP

PEER = r'''
import json,sys
pending=None
waiting=False
def emit(data):
 print(json.dumps(dict(jsonrpc='2.0',**data)),flush=True)
def reply(id,result):
 emit(dict(id=id,result=result))
def finish(id,text='DONE'):
 emit(dict(method='session/update',params=dict(sessionId='remote',update=dict(sessionUpdate='agent_message_chunk',content=dict(type='text',text=text)))))
 reply(id,dict(stopReason='end_turn'))
for line in sys.stdin:
 msg=json.loads(line); method=msg.get('method'); id=msg.get('id'); params=msg.get('params',{})
 if method=='initialize':
  assert params['clientCapabilities']['fs']['readTextFile'] is False
  assert params['clientCapabilities']['terminal'] is False
  reply(id,dict(protocolVersion=1,agentCapabilities=dict(loadSession=True)))
 elif method=='session/new': reply(id,dict(sessionId='remote'))
 elif method=='session/load':
  emit(dict(method='session/update',params=dict(update=dict(sessionUpdate='agent_message_chunk',content=dict(type='text',text='REPLAY MUST NOT DUPLICATE')))))
  reply(id,{})
 elif method=='session/set_model': reply(id,{})
 elif method=='session/prompt':
  pending=id
  text=params['prompt'][0]['text']
  if text=='permission':
   waiting=True
   emit(dict(id='permission-1',method='session/request_permission',params=dict(sessionId='remote',toolCall=dict(title='Read'),options=[dict(optionId='once',name='Allow once') ,dict(optionId='reject',name='Reject') ])))
  elif text!='hang': finish(id)
 elif method=='session/cancel':
  if pending: reply(pending,dict(stopReason='cancelled')); pending=None
 elif id=='permission-1':
  assert msg['result']['outcome']['outcome'] in ('selected','cancelled')
  if waiting: finish(pending,'PERMISSION RESPONDED'); waiting=False; pending=None
 else: reply(id,{})
'''

class Sessions(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        peer=self.root/'peer.py'; peer.write_text(PEER)
        self.command=[sys.executable,'-u',str(peer)]
        self.client=ACP(self.root/'state.db',command=self.command)

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def wait(self,id,status):
        for attempt in range(200):
            result=self.client.read(id)
            if result['session']['status']==status and (status in ('working','permission') or id not in self.client.active):
                return result
            time.sleep(.01)
        self.fail(str(result))

    def test_prompt_send_resume(self):
        id=self.client.spawn('hello',str(self.root))['id']
        result=self.wait(id,'idle')
        self.assertIn('OpenCode: DONE',result['output'])
        self.assertEqual(result['session']['acp_id'],'remote')
        self.assertEqual(result['session']['tool'],'opencode')
        self.assertFalse(result['session']['busy'])
        self.client.close()
        self.client=ACP(self.root/'state.db',command=self.command)
        self.client.resume(id)
        result=self.wait(id,'idle')
        self.assertIn('OpenCode: DONE',result['output'])
        self.client.send(id,'next')
        self.assertEqual(self.wait(id,'idle')['output'].count('OpenCode: DONE'),2)

    def test_explicit_permission_and_busy(self):
        id=self.client.spawn('permission',str(self.root))['id']
        result=self.wait(id,'permission')
        self.assertNotIn('PERMISSION RESPONDED',result['output'])
        self.assertEqual(result['permissions'][0]['request'],'permission-1')
        self.assertTrue(result['session']['busy'])
        with self.assertRaises(ValueError): self.client.send(id,'next')
        with self.assertRaises(ValueError): self.client.permission(id,'permission-1','invented')
        self.client.permission(id,'permission-1','once')
        self.assertIn('PERMISSION RESPONDED',self.wait(id,'idle')['output'])

    def test_cancel_and_restart_no_repeat(self):
        id=self.client.spawn('hang',str(self.root))['id']
        self.wait(id,'working')
        self.client.cancel(id)
        self.wait(id,'cancelled')
        session=self.client.session(id); session['status']='working'; session['permissions']=[{'request':'stale'}]; self.client.save(session)
        self.client.close()
        self.client=ACP(self.root/'state.db',command=self.command)
        self.assertEqual(self.client.read(id)['session']['status'],'interrupted')
        self.assertEqual(self.client.read(id)['permissions'],[])
        self.assertEqual(len([event for event in self.client.read(id)['events'] if event['type']=='user']),1)
        self.assertEqual(self.client.clients,{})

    def test_startup_failure_preserves_prompt(self):
        self.client.close()
        self.client=ACP(self.root/'state.db',command=['/does/not/exist'])
        id=self.client.spawn('Full request survives failed startup',str(self.root))['id']
        result=self.wait(id,'error')
        self.assertIn('Full request survives failed startup',result['output'])
        self.assertEqual(len([event for event in result['events'] if event['type']=='user']),1)

    def test_validation(self):
        with self.assertRaises(ValueError): self.client.spawn('',str(self.root))
        with self.assertRaises(ValueError): self.client.spawn('hi','relative')
        with self.assertRaises(ValueError): self.client.read('unknown')

if __name__=='__main__': unittest.main()
