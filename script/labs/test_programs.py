import json
from pathlib import Path
import tempfile
import unittest
from programs import Programs

class ProgramTest(unittest.TestCase):
    def test_literal_inputs_and_allowlist(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'host'
            path.write_text('#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps({"args":sys.argv[1:],"input":sys.stdin.read()}))\n')
            path.chmod(0o700)
            host = Programs(path)
            result = host.action('artifact-design', 'run', {'inputs': {'title': '$(false)', 'body': '`literal`'}})
            self.assertEqual(result['result']['args'], ['run', 'artifact-design', '--input', '-'])
            self.assertEqual(json.loads(result['result']['input'])['title'], '$(false)')
            with self.assertRaises(ValueError): host.action('../bad', 'run', {'inputs': {}})
            with self.assertRaises(ValueError): host.action('artifact-design', 'promote', {})
            with self.assertRaises(ValueError): host.action('artifact-design', 'run', {'inputs': []})

    def test_unavailable_host_is_sanitized(self):
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            Programs('/missing-secret-path').list()
