import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer

from server import Handler, Workspace


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / 'workspace.sqlite')
        self.workspace = Workspace(self.path, '/nonexistent-agent-manager')

    def tearDown(self):
        self.temp.cleanup()

    def create(self):
        return self.workspace.action('/api/threads', {'product': 'labs', 'title': 'Thread UX', 'outcome': 'Keep work and review together'})

    def test_persistence_and_notes(self):
        thread = self.create()
        route = '/api/threads/' + thread['id']
        self.workspace.action(route + '/note', {'body': '<script>example</script>'})
        reopened = Workspace(self.path).thread(thread['id'])
        self.assertEqual(reopened['messages'][1]['body'], '<script>example</script>')
        self.assertEqual(reopened['state'], 'draft')
        self.assertEqual(len(reopened['messages']), 2)

    def test_review_requires_evidence_and_explicit_acceptance(self):
        thread = self.create()
        route = '/api/threads/' + thread['id'] + '/state'
        with self.assertRaises(ValueError):
            self.workspace.action(route, {'state': 'resolved', 'evidence': 'bypass'})
        self.workspace.action(route, {'state': 'active'})
        with self.assertRaises(ValueError):
            self.workspace.action(route, {'state': 'review'})
        self.workspace.action(route, {'state': 'review', 'evidence': 'Candidate abc123, checks pass'})
        self.assertEqual(Workspace(self.path).thread(thread['id'])['state'], 'review')
        with self.assertRaises(ValueError):
            self.workspace.action(route, {'state': 'resolved'})
        self.workspace.action(route, {'state': 'resolved', 'evidence': 'Accepted abc123'})
        self.workspace.action(route, {'state': 'archived'})
        self.workspace.action(route, {'state': 'draft'})
        self.assertEqual(self.workspace.thread(thread['id'])['state'], 'draft')

    def test_runtime_outage_preserves_threads(self):
        self.create()
        result = self.workspace.snapshot()
        self.assertTrue(result['error'])
        self.assertEqual(result['sessions'], [])
        self.assertEqual(len(result['threads']), 1)

    def test_invalid_product_and_payload(self):
        for body in ([], {'product': 'unknown', 'title': 'Title', 'outcome': 'Outcome'}, {'product': 'labs', 'title': '', 'outcome': 'Outcome'}):
            with self.assertRaises(ValueError):
                self.workspace.action('/api/threads', body)
        with self.assertRaises(ValueError):
            self.workspace.thread('missing')

    def test_origin_host_and_static_allowlist(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.workspace = self.workspace
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        host = '127.0.0.1:' + str(server.server_port)
        def request(method, path, body=None, headers=None):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port)
            connection.request(method, path, body, headers or {})
            response = connection.getresponse()
            result = response.status, response.read()
            connection.close()
            return result
        try:
            self.assertEqual(request('GET', '/')[0], 200)
            self.assertEqual(request('GET', '/server.py')[0], 404)
            self.assertEqual(request('GET', '/../../etc/passwd')[0], 404)
            self.assertEqual(request('GET', '/api/workspace', headers={'Host': 'evil.example'})[0], 403)
            payload = json.dumps({'product': 'labs', 'title': 'HTTP', 'outcome': 'Persists over HTTP'})
            self.assertEqual(request('POST', '/api/threads', payload, {'Content-Type': 'application/json'})[0], 403)
            self.assertEqual(request('POST', '/api/threads', payload, {'Content-Type': 'application/json', 'Origin': 'https://evil.example'})[0], 403)
            code, body = request('POST', '/api/threads', payload, {'Content-Type': 'application/json', 'Origin': 'http://' + host})
            self.assertEqual(code, 200)
            key = json.loads(body)['id']
            self.assertEqual(request('GET', '/api/threads/' + key)[0], 200)
            self.assertEqual(request('POST', '/api/threads', '[]', {'Content-Type': 'application/json', 'Origin': 'http://' + host})[0], 400)
        finally:
            server.shutdown()
            server.server_close()
            worker.join()


if __name__ == '__main__':
    unittest.main()
