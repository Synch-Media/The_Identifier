"""Verify captured Milestone 1 runs against live history and model-input traces.

Read-only Langflow calls. Records image hashes instead of base64 image contents.
"""

import base64
import copy
import hashlib
import http.cookiejar
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, ProxyHandler, build_opener

from PIL import Image

from integration_probe import NoRedirect
from integration_run import BASE, FLOW, ROOT, extract_final, save


def walk_spans(spans):
    for span in spans:
        yield span
        yield from walk_spans(span.get('children', []))


def image_hashes(value):
    found = set()
    if isinstance(value, dict):
        for child in value.values():
            found.update(image_hashes(child))
    elif isinstance(value, list):
        for child in value:
            found.update(image_hashes(child))
    elif isinstance(value, str) and value.startswith('data:image/') and ';base64,' in value:
        found.add(hashlib.sha256(base64.b64decode(value.split(',', 1)[1], validate=True)).hexdigest())
    return found


def redact(value):
    if isinstance(value, dict):
        return {key: ('[REDACTED]' if key.lower() in {'api_key', 'password', 'access_token', 'refresh_token', 'secret'}
                      else redact(child)) for key, child in value.items()}
    if isinstance(value, list):
        return [redact(child) for child in value]
    if isinstance(value, str) and value.startswith('data:image/') and ';base64,' in value:
        return {'image_sha256': next(iter(image_hashes(value))), 'base64_omitted': True}
    return value


def human_texts(value):
    if isinstance(value, list):
        return [text for child in value for text in human_texts(child)]
    if isinstance(value, dict):
        if value.get('type') == 'human':
            content = value['content']
            return [content if isinstance(content, str) else ''.join(
                part.get('text', '') for part in content if part.get('type') == 'text')]
        return [text for child in value.values() for text in human_texts(child)]
    return []


def main():
    root = ROOT / 'data' / 'integration'
    cases = []
    for path in sorted(root.glob('*/summary.json')):
        summary = json.loads(path.read_text(encoding='utf-8'))
        if summary.get('outcome') == 'response_captured':
            cases.append((path.parent, summary))
    if not cases:
        raise ValueError('No captured recognition runs to verify')
    output = root / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-verification')
    output.mkdir(exist_ok=False)
    opener = build_opener(ProxyHandler({}), NoRedirect(), HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def get(path):
        with opener.open(BASE + path, timeout=30) as response:
            return json.load(response)

    get('/api/v1/auto_login')
    expected = {}
    expected_texts = {}
    report = {'runs': [], 'sessions': [], 'negative_extraction_checks': []}
    for folder, summary in cases:
        session = summary['session_id']
        expected.setdefault(session, set())
        request = json.loads((folder / 'request.json').read_text(encoding='utf-8'))
        expected_texts.setdefault(session, []).append(request['input_request']['input_value'])
        for image in summary['images']:
            original = folder / image['original']
            assert hashlib.sha256(original.read_bytes()).hexdigest() == image['original_sha256']
            assert original.read_bytes() == Path(image['source']).read_bytes()
            normalized = folder / image['normalized_jpeg']
            with Image.open(normalized) as decoded:
                assert decoded.format == 'JPEG' and decoded.mode == 'RGB'
                assert list(decoded.size) == image['size']
            expected[session].add(hashlib.sha256(normalized.read_bytes()).hexdigest())
        response = json.loads((folder / 'response.json').read_text(encoding='utf-8'))
        assert extract_final(response, session) == (folder / 'final.txt').read_text(encoding='utf-8')
        assert summary['temporary_key_revoked'] and summary['flow_graph_unchanged']
        message = response['outputs'][0]['outputs'][0]['results']['message']
        trace = get('/api/v1/monitor/traces/' + message['run_id'])
        assert trace['sessionId'] == session and trace['flowId'] == FLOW
        model_spans = [s for s in walk_spans(trace['spans']) if s.get('type') == 'llm' and s.get('modelName')]
        tool_names = [s.get('name') for s in walk_spans(trace['spans']) if s.get('type') == 'tool']
        assert model_spans, 'No recorded model-input span; image continuity not proved'
        model_checks = []
        for span in model_spans:
            observed = image_hashes(span['inputs'])
            assert observed == expected[session], 'Model-input image set differs from this session evidence'
            assert human_texts(span['inputs']) == expected_texts[session], 'Model-input user turns differ from this session'
            assert span['modelName'] == 'google/gemma-4-26b-a4b-qat'
            model_checks.append({'model': span['modelName'], 'image_sha256': sorted(observed)})
        save(output / (summary['label'] + '-trace.json'), redact(trace))
        report['runs'].append({'label': summary['label'], 'session_id': session,
                               'run_id': message['run_id'], 'final_extraction': 'pass',
                               'originals_preserved_and_jpeg_valid': True,
                               'model_inputs_match_cumulative_session_images': True,
                               'model_user_turns_match_this_session_only': True,
                               'model_calls': model_checks, 'tool_span_names': tool_names})
        print(summary['label'], 'PASS: model input contains', len(expected[session]),
              'expected image(s);', len(model_spans), 'model call(s); tools:', tool_names, flush=True)

    # Live histories must contain only images belonging to the requested session.
    for session, hashes in expected.items():
        messages = get('/api/v1/monitor/messages?' + urlencode({'flow_id': FLOW, 'session_id': session}))
        observed = set()
        assert messages and all(m['session_id'] == session for m in messages)
        for message in messages:
            files = message.get('files') or []
            if isinstance(files, str):
                files = json.loads(files)
            for file in files:
                observed.add(hashlib.sha256(Path(file).read_bytes()).hexdigest())
        assert observed == hashes
        save(output / (session + '-messages.json'), messages)
        report['sessions'].append({'session_id': session, 'message_count': len(messages),
                                   'image_sha256': sorted(observed), 'history_isolation': 'pass'})
    sessions = list(expected)
    assert len(sessions) == 2 and expected[sessions[0]].isdisjoint(expected[sessions[1]])
    live_key_ids = {key['id'] for key in get('/api/v1/api_key/')['api_keys']}
    assert all(summary['temporary_key_id'] not in live_key_ids for _, summary in cases)
    report['temporary_keys_absent_from_live_key_list'] = True
    original = Path(r'D:\LocalAI\Langflow\Exports\Identifier_LM Studio_Gamma.json').read_bytes()
    preserved = (ROOT / 'reference/langflow/Identifier_LM Studio_Gamma.json').read_bytes()
    assert original == preserved
    report['preserved_export_sha256'] = hashlib.sha256(original).hexdigest()

    # Exercise the actual final-output extraction boundary with adversarial envelopes.
    fixture = json.loads((cases[0][0] / 'response.json').read_text(encoding='utf-8'))
    session = cases[0][1]['session_id']
    for kind in ['wrong_session', 'missing_output', 'duplicate_output', 'empty_text', 'wrong_sender', 'error', 'partial']:
        value = copy.deepcopy(fixture)
        outputs = value['outputs'][0]['outputs']
        message = outputs[0]['results']['message']
        if kind == 'wrong_session': value['session_id'] = 'another-product'
        elif kind == 'missing_output': outputs.clear()
        elif kind == 'duplicate_output': outputs.append(copy.deepcopy(outputs[0]))
        elif kind == 'empty_text': message['text'] = ''
        elif kind == 'wrong_sender': message['sender'] = 'User'
        elif kind == 'error': message['error'] = True
        elif kind == 'partial': message['properties']['state'] = 'partial'
        try:
            extract_final(value, session)
        except ValueError:
            report['negative_extraction_checks'].append({'case': kind, 'outcome': 'rejected'})
        else:
            raise AssertionError('Unsafe envelope accepted: ' + kind)
    report['outcome'] = 'pass'
    save(output / 'verification.json', report)
    print('Live history isolation and seven negative extraction checks: PASS', flush=True)
    print('Evidence:', output, flush=True)


if __name__ == '__main__':
    main()
