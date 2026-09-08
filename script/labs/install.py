#!/usr/bin/env python3
"""Install the private Labs UI as a persistent user service."""
import hashlib
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parent
state = Path.home() / '.opencode2-profiles/work/state/labs'
label = 'intuitxn.labs-workspace'
state.mkdir(parents=True, exist_ok=True, mode=0o700)
os.chmod(state, 0o700)
files = [p for p in root.iterdir() if p.suffix in ('.py', '.js', '.css', '.html') and not p.name.startswith('test_')]
digest = hashlib.sha256(b''.join(p.name.encode() + p.read_bytes() for p in sorted(files))).hexdigest()[:16]
release = state / 'releases' / digest
release.mkdir(parents=True, exist_ok=True)
for file in files:
    shutil.copyfile(file, release / file.name)
env = {'HOME': str(Path.home()), 'PATH': str(Path.home()/'.local/bin') + ':/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin'}
# Agent Manager routes commands through the existing manager session.
for key in ('AGENT_MANAGER_SESSION_ID', 'TMUX', 'TMUX_PANE'):
    if os.environ.get(key): env[key] = os.environ[key]
args = ['/usr/bin/env', '-i'] + [k+'='+v for k,v in env.items()] + [str(Path(sys.executable).resolve()), str(release/'server.py'), '--database', str(state/'workspace.sqlite')]
plist = Path.home()/'Library/LaunchAgents'/(label+'.plist')
plist.write_bytes(plistlib.dumps({'Label':label, 'ProgramArguments':args, 'WorkingDirectory':str(release), 'RunAtLoad':True, 'KeepAlive':True, 'ThrottleInterval':10, 'StandardOutPath':str(state/'service.log'), 'StandardErrorPath':str(state/'service.log')}))
plist.chmod(0o600)
domain = 'gui/'+str(os.getuid())
subprocess.run(['launchctl','bootout',domain+'/'+label],capture_output=True)
import time
for attempt in range(6):
    result = subprocess.run(['launchctl','bootstrap',domain,str(plist)],capture_output=True)
    if result.returncode == 0: break
    time.sleep(1)
else:
    raise SystemExit('Could not install Labs service. Inspect '+str(state/'service.log'))
print('Installed '+label+' at http://127.0.0.1:4100')
