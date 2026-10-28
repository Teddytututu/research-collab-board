"""Private-role, media and public-projection boundaries with fictional fixtures."""
import base64
import concurrent.futures
import http.client
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from PIL import Image
from board import app, private_notes as private, project, storage

ROOT = Path(__file__).resolve().parents[1]
(ROOT / 'work/tests').mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(ROOT / 'work/tests')


def picture():
    data = io.BytesIO()
    Image.new('RGB', (12, 8), 'blue').save(data, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(data.getvalue()).decode()


class PrivateChat(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        project.initialize(self.root, 'Example private study')
        project.post(self.root, 'GPT', 'Public example')

    def post(self, peer='GPT', actor='owner', body='Private example', images=None, client='x'*32):
        return private.publish(self.root, actor, peer, dict(body=body, images=images or [], client_id=client))

    def test_owner_and_matching_assistant_can_read_and_reply(self):
        for peer in private.PEERS:
            owner = self.post(peer)
            assistant = self.post(peer, peer, 'Assistant example')
            for actor in ['owner', peer]:
                self.assertEqual([x['id'] for x in private.history(self.root, actor, peer)['items']], [owner['id'], assistant['id']])
            self.assertEqual(owner['author'], 'owner')
            self.assertEqual(assistant['author'], peer)

    def test_cross_peer_roles_reject_reads_writes_and_images(self):
        row = self.post(images=[picture()])
        for operation in [lambda: private.history(self.root, 'Claude', 'GPT'),
                          lambda: self.post('GPT', 'Claude'),
                          lambda: private.image(self.root, 'Claude', 'GPT', row['images'][0]),
                          lambda: private.history(self.root, 'guest', 'GPT')]:
            with self.assertRaises(PermissionError):
                operation()

    def test_no_private_content_in_public_projections_and_source_ledgers_preserved(self):
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file() and p.name != '.write.lock'}
        self.post(images=[picture()])
        self.assertEqual([x['body'] for x in app.conversation(self.root)['items']], ['Public example'])
        self.assertNotIn('Private example', json.dumps(app.snapshot(self.root)))
        for path, raw in before.items():
            self.assertEqual(path.read_bytes(), raw, str(path))

    def test_retry_is_idempotent_and_changed_content_rejected(self):
        row = self.post(images=[picture()])
        self.assertEqual(self.post(images=[picture()]), row)
        self.assertEqual(len(list(private.directory(self.root).rglob('*.png'))), 1)
        with self.assertRaises(ValueError):
            self.post(body='Changed')
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            rows = list(pool.map(lambda _: self.post(images=[picture()]), range(5)))
        self.assertEqual({x['id'] for x in rows}, {row['id']})

    def test_image_requires_matching_ledger_and_peer(self):
        row = self.post(images=[picture()])
        path = private.image(self.root, 'GPT', 'GPT', row['images'][0])
        with Image.open(path) as image:
            self.assertEqual((image.format, image.size), ('PNG', (12, 8)))
        for peer, name in [('Claude', row['images'][0]), ('GPT', '../owner-GPT.jsonl'), ('GPT', 'f'*32+'.png')]:
            with self.assertRaises(FileNotFoundError):
                private.image(self.root, 'owner', peer, name)

    def test_all_images_validated_before_any_write(self):
        with self.assertRaises(ValueError):
            self.post(images=[picture(), 'data:text/plain;base64,eA=='])
        self.assertEqual(list(private.directory(self.root).rglob('*.png')), [])
        self.assertEqual(private.history(self.root, 'owner', 'GPT')['items'], [])

    def test_validation_rejects_author_spoof_and_malformed_payloads(self):
        for patch in [dict(author='Claude'), dict(body=''), dict(body='x'*6001), dict(client_id='../example'), dict(images=[picture()]*7)]:
            with self.assertRaises(ValueError):
                private.publish(self.root, 'owner', 'GPT', {'body':'Example', 'client_id':'x'*32, **patch})

    def test_cursor_and_pure_read_preserve_bytes(self):
        for at in range(103):
            self.post(body=str(at), client=str(at).zfill(32))
        snapshot = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        page = private.history(self.root, 'GPT', 'GPT')
        self.assertEqual((len(page['items']), page['has_more']), (100, True))
        earlier = private.history(self.root, 'GPT', 'GPT', page['items'][0]['id'])
        self.assertEqual([x['body'] for x in earlier['items']], ['0','1','2'])
        self.assertFalse(earlier['has_more'])
        for path, raw in snapshot.items():
            self.assertEqual(path.read_bytes(), raw)
        with self.assertRaises(ValueError):
            private.history(self.root, 'GPT', 'GPT', 'missing-cursor')

    def test_incomplete_append_is_hidden_and_blocks_further_write(self):
        row = self.post()
        path = private.ledger(self.root, 'GPT')
        with path.open('ab') as stream:
            stream.write(b'{"incomplete":')
        raw = path.read_bytes()
        self.assertEqual(private.history(self.root, 'GPT', 'GPT')['items'], [row])
        with self.assertRaises(ValueError):
            self.post(client='z'*32)
        self.assertEqual(path.read_bytes(), raw)

    def test_local_cli_reads_replies_and_rejects_other_peer(self):
        self.post()
        def call(*args):
            return subprocess.run([sys.executable, '-B', str(ROOT/'scripts/private_chat.py'), '--data-dir', str(self.root), *args], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        read = call('--actor','GPT','--peer','GPT')
        self.assertEqual(read.returncode, 0, read.stderr)
        self.assertEqual(len(json.loads(read.stdout)['items']), 1)
        self.assertEqual(call('--actor','GPT','--peer','GPT','--body','Local reply').returncode, 0)
        rejected = call('--actor','Claude','--peer','GPT')
        self.assertEqual(rejected.returncode, 1)
        self.assertIn('error', json.loads(rejected.stdout))


class PrivateHTTP(PrivateChat):
    # Keep transport tests separate from inherited storage tests.
    def setUp(self):
        super().setUp()
        self.server = app.create_server(self.root, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def request(self, path, payload=None, headers=None, method=None):
        authority = '127.0.0.1:' + str(self.server.server_port)
        supplied = {'Host':authority, 'Origin':'http://'+authority, 'Content-Type':'application/json'}
        supplied.update(headers or {})
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        connection.request(method or ('GET' if payload is None else 'POST'), path, None if payload is None else json.dumps(payload), supplied)
        result = connection.getresponse()
        value = (result.status, result.read(), dict(result.getheaders()))
        connection.close()
        return value

    def test_http_owner_only_and_same_origin(self):
        for peer in private.PEERS:
            code, raw, _ = self.request('/api/private?peer='+peer, dict(body='Browser example', client_id='h'*32))
            self.assertEqual(code, 201)
            self.assertEqual(json.loads(raw)['post']['author'], 'owner')
            self.assertEqual(self.request('/api/private?peer='+peer)[0], 200)
        for actor in ['GPT','Claude','guest']:
            self.assertEqual(self.request('/api/private?peer=GPT', headers={'X-Board-Identity':actor})[0], 403)
        self.assertEqual(self.request('/api/private?peer=GPT', dict(body='Example', client_id='k'*32), {'Origin':'http://example.invalid'})[0], 403)
        self.assertEqual(self.request('/api/private?peer=GPT', dict(body='Example', client_id='k'*32, author='GPT'))[0], 400)

    def test_http_private_images_and_public_aliases(self):
        code, raw, _ = self.request('/api/private?peer=GPT', dict(body='', images=[picture()], client_id='i'*32))
        self.assertEqual(code, 201)
        name = json.loads(raw)['post']['images'][0]
        path = '/api/private/image?peer=GPT&name='+name
        code, blob, headers = self.request(path)
        self.assertEqual(code, 200); self.assertEqual(headers['Content-Type'], 'image/png')
        self.assertIn('private', headers['Cache-Control'])
        self.assertEqual(self.request(path, method='HEAD')[0:2], (200, b''))
        for alias in ['/api/private/image?peer=Claude&name='+name, '/chat-img/'+name, '/chat-file/'+name]:
            self.assertEqual(self.request(alias)[0], 404, alias)
        relative = 'attachments/private/images/GPT/'+name
        overview = storage.read(self.root/'overview.json')
        overview['links'] = [dict(path=relative, title='Example link')]
        storage.write(self.root/'overview.json', overview)
        self.assertEqual(self.request('/files/'+relative)[0], 404)
        self.assertEqual(self.request('/api/open',dict(i=0))[0], 404)
        self.assertEqual(self.request(path, dict(body='Wrong method'))[0], 405)

    def test_http_invalid_peer_cursor_query_and_static_assets(self):
        for query in ['', '?peer=owner', '?peer=GPT&peer=Claude', '?peer=GPT&author=Claude', '?peer=GPT&before=', '?peer=GPT&before=missing']:
            self.assertEqual(self.request('/api/private'+query)[0], 400, query)
        for asset in ['/private-notes.js', '/private-notes.css']:
            self.assertEqual(self.request(asset)[0], 200)


if __name__ == '__main__':
    unittest.main()
