#!/usr/bin/env python3
"""Reference Model Context Protocol (MCP) server for the DAM capability playbooks.

Lets an MCP-compatible assistant use the portal's published content as tools. It speaks
JSON-RPC 2.0 over standard input and output (one JSON message per line), uses only the
Python standard library, and returns the page address each answer comes from.

Content comes from, in order:
  1. DAM_PLAYBOOKS_FILE: a local copy of data/playbooks.json
  2. DAM_PLAYBOOKS_URL: the published data/playbooks.json
  3. site/data/playbooks.json in this repository, after a build

This is a reference for testing and adaptation, not a supported service. It reads public,
Open Government Licence content and sends nothing anywhere except the one request for the
content file.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

SERVER = {'name': 'dam-playbooks', 'version': '1.10.1'}
DEFAULT_PROTOCOL = '2025-06-18'
REPO = Path(__file__).resolve().parents[2]
SITE = 'https://cyberdudeuk.github.io/dam-capability-playbooks/'
CAP_PAGE = {'gov': 'governance', 'cat': 'cataloguing', 'dq': 'quality'}

TOOLS = [
    {'name': 'search_portal', 'description': 'Search DAM Policy requirements, playbook steps, capabilities, delivery practices, sector supplements, tool categories and glossary terms. Returns matches with the page each comes from.',
     'inputSchema': {'type': 'object', 'properties': {'query': {'type': 'string', 'description': 'Words to look for'}, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 10}}, 'required': ['query']}},
    {'name': 'get_capability', 'description': 'Get one capability from the capability model by its identifier, such as CR-01, with how the policy states it and where to go next.',
     'inputSchema': {'type': 'object', 'properties': {'id': {'type': 'string'}}, 'required': ['id']}},
    {'name': 'get_requirement', 'description': 'Get one DAM Policy requirement by its identifier, such as DAM-R01, with its strength and source.',
     'inputSchema': {'type': 'object', 'properties': {'id': {'type': 'string'}}, 'required': ['id']}},
    {'name': 'get_practice', 'description': 'Get one delivery and change practice by its identifier, such as CH-06, with why it matters and the actions to take.',
     'inputSchema': {'type': 'object', 'properties': {'id': {'type': 'string'}}, 'required': ['id']}},
    {'name': 'list_sector_rules', 'description': 'List the starter data quality rules for a sector supplement. Without an identifier, lists the supplements.',
     'inputSchema': {'type': 'object', 'properties': {'id': {'type': 'string', 'description': 'Supplement identifier; omit to list them'}}}},
]


def load():
    f = os.environ.get('DAM_PLAYBOOKS_FILE')
    if f:
        return json.loads(Path(f).read_text(encoding='utf-8'))
    url = os.environ.get('DAM_PLAYBOOKS_URL')
    if url:
        if not url.startswith('https://'):
            raise ValueError('DAM_PLAYBOOKS_URL must use https')
        with urllib.request.urlopen(url, timeout=30) as r:  # noqa: S310 - https only, checked above
            return json.loads(r.read().decode('utf-8'))
    local = REPO / 'site' / 'data' / 'playbooks.json'
    if local.exists():
        return json.loads(local.read_text(encoding='utf-8'))
    raise FileNotFoundError('Set DAM_PLAYBOOKS_FILE or DAM_PLAYBOOKS_URL, or build the site first')


class Portal:
    def __init__(self, d):
        self.d = d
        self.base = d.get('meta', {}).get('site_url', SITE)

    def url(self, page, anchor=''):
        return f'{self.base}{page}.html' + (f'#{anchor}' if anchor else '')

    def records(self):
        d = self.d
        for r in d.get('requirements', []):
            yield 'requirement', r['id'], r['text'], self.url('dam', r['id'])
        for c in d.get('capabilities', []):
            for st in c.get('stages', []):
                yield 'step', f'{c["id"]}-{st["id"]}', f'{c["name"]} step {st["n"]}: {st["name"]}. {st["goal"]} ' + ' '.join(st.get('steps', [])), self.url(CAP_PAGE.get(c['id'], 'index'), f'{c["id"]}-{st["id"]}')
        for c in d.get('capmap', []):
            yield 'capability', c['id'], f'{c["name"]}. {c.get("note", "")}', self.url('capability-model', c['id'])
        for x in d.get('change', {}).get('items', []):
            yield 'practice', x['id'], f'{x["title"]}. {x["why"]} ' + ' '.join(x.get('actions', [])), self.url('change', x['id'])
        for x in d.get('supplements', []):
            yield 'sector', x['id'], f'{x["title"]}. {x["summary"]}', self.url('sectors', x['id'])
        for x in d.get('tooling', {}).get('categories', []):
            yield 'tool category', x['id'], f'{x["name"]}. {x["what"]} Ask: {x["ask"]}', self.url('tooling', x['id'])
        for c in d.get('concepts', []):
            yield 'term', c['id'], f'{c["term"]}: {c["def"]}', self.url('knowledge', 'c-' + c['id'])

    def search_portal(self, query, limit=10):
        words = [w for w in query.lower().split() if w]
        if not words:
            raise ValueError('query must contain at least one word')
        scored = []
        for kind, rid, text, url in self.records():
            low = text.lower()
            score = sum(low.count(w) for w in words) + (5 if rid.lower() in words else 0)
            if score and all(w in low or w == rid.lower() for w in words):
                scored.append((score, {'kind': kind, 'id': rid, 'text': text[:400], 'url': url}))
        scored.sort(key=lambda s: -s[0])
        return {'query': query, 'matches': [s[1] for s in scored[:max(1, min(int(limit), 50))]]}

    def _one(self, items, rid, what):
        for x in items:
            if x['id'].lower() == rid.lower():
                return x
        raise KeyError(f'no {what} with identifier {rid}')

    def get_capability(self, id):
        c = self._one(self.d.get('capmap', []), id, 'capability')
        return {'id': c['id'], 'name': c['name'], 'flag': c['flag'], 'note': c.get('note'), 'coverage': c.get('coverage'),
                'signposts': c.get('signposts', []), 'url': self.url('capability-model', c['id'])}

    def get_requirement(self, id):
        r = self._one(self.d.get('requirements', []), id, 'requirement')
        src = next((s for s in self.d.get('sources', []) if s['id'] == r['src']), {})
        return {'id': r['id'], 'strength': r['strength'], 'text': r['text'], 'source': src.get('title'), 'source_url': src.get('url'), 'url': self.url('dam', r['id'])}

    def get_practice(self, id):
        x = self._one(self.d.get('change', {}).get('items', []), id, 'practice')
        return {'id': x['id'], 'title': x['title'], 'why': x['why'], 'actions': x['actions'], 'evidence': x.get('evidence'), 'url': self.url('change', x['id'])}

    def list_sector_rules(self, id=None):
        sups = self.d.get('supplements', [])
        if not id:
            return {'supplements': [{'id': x['id'], 'title': x['title'], 'rules': len(x.get('rules', [])), 'url': self.url('sectors', x['id'])} for x in sups]}
        x = self._one(sups, id, 'sector supplement')
        return {'id': x['id'], 'title': x['title'], 'rules': x.get('rules', []), 'url': self.url('sectors', x['id'])}


def handle(portal, msg):
    """Return a response for one JSON-RPC message, or None for a notification."""
    mid, method, params = msg.get('id'), msg.get('method'), msg.get('params') or {}
    if mid is None:
        return None
    try:
        if method == 'initialize':
            result = {'protocolVersion': params.get('protocolVersion') or DEFAULT_PROTOCOL, 'capabilities': {'tools': {}}, 'serverInfo': SERVER,
                      'instructions': 'Content from the DAM capability playbooks prototype. Cite the url returned with each answer; GOV.UK is the authority.'}
        elif method == 'ping':
            result = {}
        elif method == 'tools/list':
            result = {'tools': TOOLS}
        elif method == 'tools/call':
            name, args = params.get('name'), params.get('arguments') or {}
            if name not in {t['name'] for t in TOOLS}:
                return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32602, 'message': f'unknown tool {name}'}}
            try:
                out = getattr(portal, name)(**args)
                result = {'content': [{'type': 'text', 'text': json.dumps(out, ensure_ascii=False)}], 'structuredContent': out, 'isError': False}
            except (KeyError, ValueError, TypeError) as e:
                result = {'content': [{'type': 'text', 'text': str(e).strip("'")}], 'isError': True}
        else:
            return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32601, 'message': f'method not found: {method}'}}
        return {'jsonrpc': '2.0', 'id': mid, 'result': result}
    except Exception as e:  # keep the server alive on unexpected input
        return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32603, 'message': str(e)}}


def main():
    portal = Portal(load())
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            resp = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'parse error'}}
        else:
            resp = handle(portal, msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + '\n')
            sys.stdout.flush()


if __name__ == '__main__':
    main()
