"""Read-only verification of explicitly captured Milestone 2 browser runs.

Usage: python -m scripts.milestone2_verify <browser-report.json> [...]
No recognition executions, uploads, or configuration changes.
"""
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import urlencode

from backend.langflow import LangflowClient
from backend.main import ROOT
from scripts.integration_run import FLOW

# Reuse Milestone 1's actual model-input image and message inspectors.
sys.path.insert(0, str(ROOT / 'scripts'))
from integration_verify import image_hashes, human_texts, walk_spans


def main():
    session_ids = []
    for report_path in sys.argv[1:]:
        report = json.loads(Path(report_path).read_text())
        assert report['outcome'] == 'passed'
        session_ids.extend(report.get('sessions', []))
        if report.get('session'):
            session_ids.append(report['session'])
    assert session_ids
    client = LangflowClient()
    client.call('/api/v1/auto_login')
    report = {'sessions': [], 'checks': {}}
    all_sets = []
    for session_id in session_ids:
        directory = ROOT / 'data/sessions' / session_id
        session = json.loads((directory / 'session.json').read_text(encoding='utf-8'))
        langflow_id = session['langflow_session_id']
        query = urlencode({'flow_id': FLOW, 'session_id': langflow_id})
        messages = client.call('/api/v1/monitor/messages?' + query)
        assert all(m['session_id'] == langflow_id for m in messages)
        assert len(messages) == len(session['attempts']) * 2
        traces = client.call('/api/v1/monitor/traces?' + query)['traces']
        traces.sort(key=lambda trace: trace['startTime'])
        assert len(traces) == len(session['attempts'])
        expected_hashes, expected_turns = set(), []
        checks = []
        for attempt, trace_summary in zip(session['attempts'], traces):
            expected_hashes.update(hashlib.sha256((directory / (image_id + '.jpg')).read_bytes()).hexdigest()
                                   for image_id in attempt['image_ids'])
            expected_turns.append(trace_summary['input']['input_value'])
            trace = client.call('/api/v1/monitor/traces/' + trace_summary['id'])
            assert trace['sessionId'] == langflow_id and trace['flowId'] == FLOW
            spans = list(walk_spans(trace['spans']))
            models = [s for s in spans if s.get('type') == 'llm' and s.get('modelName')]
            assert models
            for span in models:
                assert span['modelName'] == 'google/gemma-4-26b-a4b-qat'
                assert image_hashes(span['inputs']) == expected_hashes
                assert human_texts(span['inputs']) == expected_turns
            checks.append({'attempt': attempt['number'], 'result': attempt['parsed_result']['status'],
                           'runtime_seconds': attempt['runtime_seconds'], 'model_calls': len(models),
                           'image_count': len(expected_hashes), 'user_turn_count': len(expected_turns),
                           'tools': [s.get('name') for s in spans if s.get('type') == 'tool'],
                           'images_and_user_turns_match_session': True})
        all_sets.append(expected_hashes)
        report['sessions'].append({'id': session_id, 'langflow_session_id': langflow_id,
                                   'message_count': len(messages), 'runs': checks})
    # Jeans versus first shoes: truly distinct products and evidence.
    assert all_sets[0].isdisjoint(all_sets[1])
    report['checks']['distinct_product_images_disjoint'] = True
    flow = client.call('/api/v1/flows/' + FLOW)
    before = json.loads((ROOT / 'data/milestone2/flow-before.json').read_text())
    assert flow['data'] == before['data']
    report['checks']['live_flow_graph_unchanged'] = True
    key_ids = [key['id'] for key in client.call('/api/v1/api_key/')['api_keys']]
    baseline = json.loads((ROOT / 'data/milestone2/keys-before.json').read_text())
    assert set(key_ids) == set(baseline)
    report['checks']['temporary_keys_absent'] = True
    original = Path(r'D:\LocalAI\Langflow\Exports\Identifier_LM Studio_Gamma.json').read_bytes()
    reference = (ROOT / 'reference/langflow/Identifier_LM Studio_Gamma.json').read_bytes()
    assert original == reference
    checksum = hashlib.sha256(reference).hexdigest()
    assert checksum == '9cb629b672f9b63dc454be4b9b25fd83032b7be156944894d62363e3216a2006'
    report['checks']['export_sha256'] = checksum
    report['outcome'] = 'passed'
    (ROOT / 'data/milestone2/verification.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
