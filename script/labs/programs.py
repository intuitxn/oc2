"""Explicit, allowlisted calls to the installed Nudge OS program host."""
import json
from pathlib import Path
import subprocess
import tempfile


class Programs:
    names = ('artifact-design', 'lesson-proposal', 'lesson-review')

    def __init__(self, binary=None):
        self.binary = str(binary or Path.home() / '.local/bin/telepathy-program')

    def invoke(self, args, value=None):
        with tempfile.TemporaryFile() as output:
            try:
                result = subprocess.run([self.binary, *args], input=json.dumps(value) if value is not None else '', text=True, stdout=output, stderr=subprocess.DEVNULL, timeout=110)
            except (OSError, subprocess.TimeoutExpired) as err:
                raise ValueError('Program host unavailable or timed out. No result was accepted.') from err
            if output.tell() > 1000000:
                raise ValueError('Program response exceeds the display limit.')
            output.seek(0)
            try:
                data = json.load(output)
            except (ValueError, UnicodeDecodeError) as err:
                raise ValueError('Program host returned an unreadable result.') from err
            return {'code': result.returncode, 'result': data}

    def list(self):
        result = self.invoke(['list'])
        if result['code']:
            raise ValueError('Program catalog unavailable.')
        return result['result']

    def action(self, name, action, body):
        if name not in self.names or action not in ('compile', 'run') or not isinstance(body, dict):
            raise ValueError('Choose a supported program action.')
        if action == 'compile':
            return self.invoke(['compile', name])
        value = body.get('inputs')
        if not isinstance(value, dict):
            raise ValueError('Program inputs must be a JSON object matching its contract.')
        return self.invoke(['run', name, '--input', '-'], value)
