"""Fixture-only withdrawal permissions, immutable storage and API projection."""
import http.client
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from board import project, storage, contacts
from board.app import create_server, conversation

ROOT = Path(__file__).resolve().parents[1]


class Deletion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        project.initialize(self.root, 'Deletion fixture')
        self.image = 'a' * 32 + '.png'
        self.file = 'b' * 32 + '.txt'
        for folder, name in [('images', self.image), ('files', self.file)]:
            path = self.root / 'attachments/discussion' / folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'RETAINED_ATTACHMENT')
        self.message = project.post(self.root, 'GPT', 'WITHDRAWN_SECRET', client_id='a' * 32,
                                    images=[self.image], files=[{'id': self.file, 'name': 'SECRET_FILE.txt', 'url': '/chat-file/' + self.file, 'bytes': 19}])
        self.server = create_server(self.root, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def req(self, route, payload=None, headers=None):
        port = self.server.server_port
        values = {'Host': f'127.0.0.1:{port}', 'Origin': f'http://127.0.0.1:{port}', 'Content-Type': 'application/json'}
        values.update(headers or {})
        client = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        client.request('POST' if payload is not None else 'GET', route, json.dumps(payload) if payload is not None else None, values)
        reply = client.getresponse(); raw = reply.read(); code = reply.status; client.close()
        return code, raw

    def test_tombstone_preserves_raw_and_propagates_saved_reference(self):
        saved = project.bookmark(self.root, 'main', self.message['id'])
        reply = project.post(self.root, 'Claude', 'Own reply remains', parent_id=self.message['id'])
        before = {c: project.ledger(self.root, c).read_bytes() for c in project.CHANNELS if project.ledger(self.root, c).exists()}
        deleted = project.delete_message(self.root, self.message['id'], 'GPT', assistant=True)
        self.assertTrue(deleted['deleted'])
        self.assertEqual(deleted, project.delete_message(self.root, self.message['id'], 'GPT', assistant=True))
        items = {p['id']: p for p in conversation(self.root)['items']}
        for mid in (self.message['id'], saved['id']):
            self.assertTrue(items[mid]['deleted']); self.assertEqual(items[mid]['body'], '')
            self.assertEqual(items[mid]['images'], []); self.assertEqual(items[mid]['files'], [])
            self.assertFalse(items[mid]['can_delete'])
            self.assertNotIn('reference', items[mid])
        self.assertTrue(items[reply['id']]['parent_deleted'])
        self.assertEqual(items[reply['id']]['body'], 'Own reply remains')
        for c, raw in before.items(): self.assertEqual(project.ledger(self.root, c).read_bytes(), raw)
        self.assertEqual((self.root / 'attachments/discussion/images' / self.image).read_bytes(), b'RETAINED_ATTACHMENT')

    def test_assistant_self_only_and_owner_admin(self):
        with self.assertRaises(PermissionError):
            project.delete_message(self.root, self.message['id'], 'Claude', assistant=True)
        with self.assertRaises(PermissionError):
            project.delete_message(self.root, self.message['id'], 'owner', assistant=True)
        code, raw = self.req('/api/discussion/delete', {'message_id': self.message['id']})
        self.assertEqual(code, 200, raw)
        self.assertEqual(json.loads(raw)['deleted_by'], 'owner')
        self.assertEqual(conversation(self.root)['items'][0]['delete_action'], 'delete')

    def test_http_actor_spoofing_rejected_and_get_contract(self):
        item = conversation(self.root)['items'][0]
        self.assertTrue(item['can_delete']); self.assertFalse(item['deleted'])
        self.assertEqual(item['delete_action'], 'delete')
        own = project.post(self.root, 'owner', 'Owner own message')
        own_item = next(p for p in conversation(self.root)['items'] if p['id'] == own['id'])
        self.assertTrue(own_item['can_delete']); self.assertEqual(own_item['delete_action'], 'withdraw')
        for field in ('actor', 'author', 'deleted_by'):
            code, _ = self.req('/api/discussion/delete', {'message_id': self.message['id'], field: 'GPT'})
            self.assertIn(code, (400, 403))
        self.assertEqual(self.req('/api/discussion/delete', {'message_id': self.message['id']}, {'Origin': 'http://elsewhere.invalid'})[0], 403)

    def test_all_surfaces_retry_and_attachments_hide_original(self):
        project.bookmark(self.root, 'main', self.message['id'])
        project.delete_message(self.root, self.message['id'], 'GPT', assistant=True)
        for route in ('/api/discussion', '/api/board', '/api/conversations', '/api/discussion?channel=library'):
            code, raw = self.req(route)
            self.assertEqual(code, 200, raw)
            self.assertNotIn(b'WITHDRAWN_SECRET', raw); self.assertNotIn(b'SECRET_FILE', raw)
        for route in ('/chat-img/' + self.image, '/chat-file/' + self.file):
            self.assertEqual(self.req(route)[0], 404)
        with self.assertRaises(ValueError): contacts.download(self.root, self.file)
        with self.assertRaises(ValueError): project.bookmark(self.root, 'main', self.message['id'])
        retried = project.post(self.root, 'GPT', 'WITHDRAWN_SECRET', client_id='a' * 32, images=[self.image])
        self.assertEqual(retried['body'], '')

    def test_reactions_have_known_actors_and_unknown_count_only(self):
        path = self.root / 'attachments/discussion/reactions.jsonl'
        for row in ({'actor': 'GPT'}, {'actor': 'owner'}, {'count': 3}, {'actor': 'old-unresolved'}):
            storage.append(path, dict(message_id=self.message['id'], emoji='💡', active=True, **row))
        reaction = conversation(self.root)['items'][0]['reactions'][0]
        self.assertEqual(reaction['count'], 6)
        self.assertTrue(reaction['mine'])
        self.assertEqual({p['id'] for p in reaction['actors']}, {'owner', 'GPT'})
        for actor in reaction['actors']:
            self.assertEqual(set(actor), {'id', 'display_name', 'avatar'})
        project.delete_message(self.root, self.message['id'], 'GPT', assistant=True)
        self.assertEqual(conversation(self.root)['items'][0]['reactions'], [])
        self.assertIn(self.req('/api/reaction', {'message_id': self.message['id'], 'emoji': '💡', 'active': True})[0], (400, 404))

    def test_cli_uses_only_own_assistant_identity(self):
        command = [sys.executable, '-B', '-m', 'board', 'message', 'Claude', '--delete', self.message['id'], '--data-dir', str(self.root)]
        failed = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=20)
        self.assertNotEqual(failed.returncode, 0)
        command[5] = 'GPT'
        done = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=20)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(json.loads(done.stdout)['deleted'])

    def test_reply_quote_redaction_retains_own_body_and_blocks_index_alias(self):
        reply = project.post(self.root, 'Claude', 'Independent reply', parent_id=self.message['id'])
        path = project.ledger(self.root)
        rows = storage.lines(path)
        rows[-1]['reference'] = {'message_id': self.message['id'], 'body': 'WITHDRAWN_SECRET'}
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
        overview = storage.read(self.root / 'overview.json')
        relative = 'attachments/discussion/images/' + self.image
        overview['links'] = [{'title': 'Indexed alias', 'path': relative}]
        storage.write(self.root / 'overview.json', overview)
        project.delete_message(self.root, self.message['id'], 'GPT', assistant=True)
        projected = next(p for p in conversation(self.root)['items'] if p['id'] == reply['id'])
        self.assertFalse(projected['deleted']); self.assertEqual(projected['body'], 'Independent reply')
        self.assertEqual(projected['reference_text'], '原消息已撤回')
        self.assertNotIn('WITHDRAWN_SECRET', json.dumps(projected))
        self.assertEqual(self.req('/files/' + relative)[0], 404)
        self.assertEqual(self.req('/api/open', {'i': 0})[0], 404)

    def test_http_retry_after_withdrawal_and_identity_header(self):
        for identity in (None, 'GPT', 'Claude', 'untrusted-human'):
            headers = {'X-Board-Identity': identity} if identity else {}
            code, identity_raw = self.req('/api/me', headers=headers)
            self.assertEqual(code, 200, identity_raw)
            self.assertEqual(json.loads(identity_raw)['id'], 'owner')
        payload = {'body': 'OWNER_ORIGINAL', 'client_id': 'f' * 32}
        code, raw = self.req('/api/discussion', payload)
        self.assertEqual(code, 201, raw)
        mid = json.loads(raw)['post']['id']
        self.assertEqual(self.req('/api/discussion/delete', {'message_id': mid}, {'X-Board-Identity': 'GPT'})[0], 403)
        self.assertEqual(self.req('/api/discussion/delete', {'message_id': mid})[0], 200)
        code, raw = self.req('/api/discussion', payload)
        self.assertEqual(code, 201, raw); self.assertNotIn(b'OWNER_ORIGINAL', raw)
        self.assertTrue(json.loads(raw)['post']['deleted'])


if __name__ == '__main__': unittest.main()
