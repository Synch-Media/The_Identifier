"""One explicit Milestone 1 recognition call, with local evidence capture.

Uses the existing Desktop auto-login to create an expiring test API key, keeps
its secret only in memory, and revokes that key in finally. Never edits the flow.
Requires Pillow; uses the standard library for HTTP. No automatic run retries.
"""

import argparse
import hashlib
import http.cookiejar
import json
import shutil
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener

from PIL import Image, ImageOps

try:
    from .integration_probe import NoRedirect
except ImportError:  # Preserve direct script execution.
    from integration_probe import NoRedirect

BASE = 'http://127.0.0.1:7860'
FLOW = '88f6a048-d942-421a-af54-d297e8033806'
INPUT = 'ChatInput-TKjnK'
OUTPUT = 'ChatOutput-KxTA8'
ROOT = Path(__file__).resolve().parents[1]


def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding='utf-8')


def extract_final(response, session):
    if response.get('session_id') != session:
        raise ValueError('Integration error: response session mismatch')
    matches = [output for group in response.get('outputs', [])
               for output in group.get('outputs', [])
               if output.get('component_id') == OUTPUT]
    if len(matches) != 1:
        raise ValueError('Integration error: expected exactly one selected Chat Output')
    message = matches[0].get('results', {}).get('message', {})
    if message.get('session_id') != session or message.get('sender') != 'Machine':
        raise ValueError('Integration error: final message session or sender mismatch')
    if message.get('error') is not False or message.get('properties', {}).get('state') != 'complete':
        raise ValueError('Integration error: failed or incomplete final message')
    text = message.get('text')
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Integration error: empty/non-text final output')
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--image', type=Path, action='append', default=[])
    parser.add_argument('--text', default='Identify this product according to the Identifier workflow.')
    args = parser.parse_args()
    if not args.session.startswith('identifier-m1-'):
        parser.error('Use a new identifier-m1- prefixed test session, never a Playground session.')
    if not args.label.replace('-', '').isalnum():
        parser.error('Use a simple alphanumeric/hyphen label.')
    now = datetime.now(timezone.utc)
    folder = ROOT / 'data' / 'integration' / (now.strftime('%Y%m%dT%H%M%S%fZ') + '-' + args.label)
    folder.mkdir(parents=True, exist_ok=False)
    opener = build_opener(ProxyHandler({}), NoRedirect(),
                         HTTPCookieProcessor(http.cookiejar.CookieJar()))
    secret = None
    key_id = None

    def call(path, payload=None, headers=None, method=None, timeout=30):
        request_headers = dict(headers or {})
        if secret:
            request_headers['x-api-key'] = secret
        if isinstance(payload, dict):
            payload = json.dumps(payload).encode('utf-8')
            request_headers['Content-Type'] = 'application/json'
        request = Request(BASE + path, data=payload, headers=request_headers, method=method)
        with opener.open(request, timeout=timeout) as response:
            return response.status, json.load(response)

    summary = {'base_url': BASE, 'flow_id': FLOW, 'session_id': args.session,
               'label': args.label, 'started_at_utc': now.isoformat(), 'images': []}
    try:
        call('/api/v1/auto_login')  # Session tokens are never logged or persisted.
        _, key = call('/api/v1/api_key/', {
            'name': 'Identifier Milestone 1 temporary ' + args.label,
            'expires_at': (now + timedelta(hours=1)).isoformat(),
        })
        key_id, secret = key['id'], key['api_key']
        summary['temporary_key_id'] = key_id
        summary['key_created'] = True
        print('Temporary local API key created; secret held in memory.', flush=True)

        _, flow = call('/api/v1/flows/' + FLOW)
        save(folder / 'flow-before.json', flow)
        baseline = json.loads((ROOT / 'reference/langflow/Identifier_LM Studio_Gamma.json').read_text(encoding='utf-8'))
        before = {node['id']: node for node in baseline['data']['nodes']}
        live = {node['id']: node for node in flow['data']['nodes']}
        if before.keys() != live.keys():
            raise ValueError('Flow component IDs differ from frozen export')
        for node_id in before:
            bt = before[node_id]['data']['node'].get('template', {})
            lt = live[node_id]['data']['node'].get('template', {})
            for name, field in bt.items():
                if isinstance(field, dict) and not name.startswith('_frontend_'):
                    if field.get('value') != lt.get(name, {}).get('value'):
                        raise ValueError('Frozen flow value differs: ' + node_id + '/' + name)
        if [e['data'] for e in baseline['data']['edges']] != [e['data'] for e in flow['data']['edges']]:
            raise ValueError('Frozen flow connections differ')
        summary['frozen_values_and_connections_match'] = True

        files = []
        for index, source in enumerate(args.image):
            original_dir = folder / 'originals'
            original_dir.mkdir(exist_ok=True)
            original = original_dir / (str(index) + source.suffix.lower())
            shutil.copy2(source, original)
            jpeg = folder / ('image-' + str(index) + '.jpg')
            with Image.open(original) as image:
                if image.format not in {'JPEG', 'PNG', 'WEBP'}:
                    raise ValueError('Only JPG, PNG, and WebP test images are supported')
                image.load()
                oriented = ImageOps.exif_transpose(image)
                rgba = oriented.convert('RGBA')
                flattened = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
                flattened.alpha_composite(rgba)
                flattened.convert('RGB').save(jpeg, 'JPEG', quality=95, subsampling=0)
            filename = 'identifier-m1-' + uuid.uuid4().hex + '.jpg'
            boundary = 'identifier-' + uuid.uuid4().hex
            body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                    'Content-Type: image/jpeg\r\n\r\n').encode() + jpeg.read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
            status, uploaded = call('/api/v1/files/upload/' + FLOW, body,
                                    {'Content-Type': 'multipart/form-data; boundary=' + boundary})
            save(folder / ('upload-' + str(index) + '.json'), {'http_status': status, 'response': uploaded})
            files.append(uploaded['file_path'])
            summary['images'].append({'source': str(source), 'original': str(original.relative_to(folder)),
                                      'original_sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
                                      'normalized_jpeg': jpeg.name, 'size': list(rgba.size),
                                      'file_path': uploaded['file_path']})
            print('JPEG upload HTTP', status, 'image', index, flush=True)

        payload = {'input_request': {
            'input_value': args.text, 'input_type': 'chat', 'output_type': 'chat',
            'output_component': OUTPUT, 'session_id': args.session,
            'tweaks': {INPUT: {'files': files}},
        }}
        save(folder / 'request.json', payload)
        print('Starting ONE recognition request:', args.label, args.session, flush=True)
        start = time.monotonic()
        try:
            status, response = call('/api/v1/run/' + FLOW + '?stream=false', payload, timeout=420)
        finally:
            summary['elapsed_seconds'] = round(time.monotonic() - start, 3)
        summary['run_http_status'] = status
        save(folder / 'response.json', response)
        final = extract_final(response, args.session)
        (folder / 'final.txt').write_text(final, encoding='utf-8')
        print('Final Chat Output extracted; elapsed seconds:', summary['elapsed_seconds'], flush=True)
        print(final.encode('ascii', errors='backslashreplace').decode(), flush=True)
        _, messages = call('/api/v1/monitor/messages?' + urlencode({'flow_id': FLOW, 'session_id': args.session}))
        save(folder / 'messages.json', messages)
        if any(m.get('session_id') != args.session for m in messages):
            raise ValueError('History endpoint returned another session')
        summary['history_message_count'] = len(messages)
        _, after = call('/api/v1/flows/' + FLOW)
        save(folder / 'flow-after.json', after)
        summary['flow_graph_unchanged'] = flow['data'] == after['data']
        if not summary['flow_graph_unchanged']:
            raise ValueError('Flow graph changed during test')
        summary['outcome'] = 'response_captured'
    except HTTPError as exc:
        summary.update(outcome='integration_error', http_status=exc.code)
        raw = exc.read().decode('utf-8', errors='replace')
        if secret:
            raw = raw.replace(secret, '[REDACTED]')
        (folder / 'http-error.txt').write_text(raw, encoding='utf-8')
        print('Integration error HTTP', exc.code, flush=True)
    except Exception as exc:
        summary.update(outcome='integration_error', error_type=type(exc).__name__, detail=str(exc))
        print('Integration error:', type(exc).__name__, str(exc), flush=True)
    finally:
        if key_id:
            try:
                call('/api/v1/api_key/' + key_id, method='DELETE')
                summary['temporary_key_revoked'] = True
            except Exception as exc:
                summary['temporary_key_revoked'] = False
                summary['revocation_error_type'] = type(exc).__name__
                print('Temporary-key revocation requires attention; key expires in one hour.', flush=True)
        save(folder / 'summary.json', summary)
        print('Evidence:', folder, flush=True)
    return 0 if summary.get('outcome') == 'response_captured' and summary.get('temporary_key_revoked') else 1


if __name__ == '__main__':
    raise SystemExit(main())
