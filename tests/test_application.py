import io
import json
from pathlib import Path
from urllib.error import URLError

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import main
from backend.langflow import LangflowClient
from backend.parser import parse_final
from scripts.integration_run import extract_final

ROOT = Path(__file__).resolve().parents[1]
# Synthetic labeled outputs keep offline tests independent of private live evidence.
FIXTURES = ROOT / 'tests/fixtures/final_outputs'
NEEDS = (FIXTURES / 'needs_shoes.txt').read_text(encoding='utf-8')
RESOLVED = (FIXTURES / 'resolved_jeans.txt').read_text(encoding='utf-8')
UNRESOLVED = 'Status: Unresolved\nBrand: Unknown\nProduct Name: Unknown\nItem Type: Shoes\nCandidate: Possible model AB-12\nEvidence:\n- White shoes; AB-12 is a candidate only.\nReason Unresolved: No more evidence.\n'


class FakeLangflow:
    calls = []
    output = NEEDS
    fail = False
    cleanup_warning = None

    def authenticate(self): pass
    def upload(self, path): return path.name
    def close(self): pass
    def run(self, session, text, files):
        self.calls.append((session, text, files))
        if self.fail:
            raise URLError('SECRET upstream failure body')
        return self.output


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DATA', tmp_path)
    monkeypatch.setattr(main, 'LangflowClient', FakeLangflow)
    FakeLangflow.calls = []
    FakeLangflow.output = NEEDS
    FakeLangflow.fail = False
    with TestClient(main.app, headers={'X-Identifier-Local': '1'}) as client:
        yield client


def new(client):
    return client.post('/api/sessions').json()['id']


def upload(client, session, format='PNG'):
    output = io.BytesIO()
    Image.new('RGB' if format == 'JPEG' else 'RGBA', (10, 20), 'white').save(output, format)
    return client.post(f'/api/sessions/{session}/images', files={'file': ('sample.' + format.lower(), output.getvalue())})


def run(client, session, body=None):
    response = client.post(f'/api/sessions/{session}/identify', json=body or {})
    assert response.status_code == 202, response.text
    return client.get(f'/api/sessions/{session}').json()


@pytest.mark.parametrize('fixture', sorted(FIXTURES.glob('*.txt')))
def test_fixture_final_outputs(fixture):
    result = parse_final(fixture.read_text(encoding='utf-8'))
    assert result.status in {'Resolved', 'Needs Evidence'}


@pytest.mark.parametrize('text', [
    RESOLVED.replace('Brand:\nLevi\'s', 'Brand:\nUnknown'),
    RESOLVED.replace('Brand:\nLevi\'s', 'Brand:\nUnknown (not visible)'),
    RESOLVED + '\nStatus: Unresolved',
    NEEDS.replace('Status: Needs Evidence', 'Status: Failed'),
    NEEDS[:NEEDS.index('Next Action:')],
    'Thinking privately...\n' + NEEDS,
    NEEDS + '\nStyle Accent: Fancy',
])
def test_invalid_output_never_becomes_unresolved(text):
    with pytest.raises(ValueError): parse_final(text)


def test_bold_labels_and_candidate_preservation():
    result = parse_final(UNRESOLVED.replace('Status:', '**Status:**'))
    assert result.status == 'Unresolved'
    assert result.candidate == 'Possible model AB-12'
    assert result.product_name is None


@pytest.mark.parametrize('format', ['JPEG', 'PNG', 'WEBP'])
def test_formats_and_removal(client, format):
    session = new(client)
    response = upload(client, session, format)
    assert response.status_code == 201
    image = response.json()['images'][0]
    preview = client.get(f'/api/sessions/{session}/images/{image["id"]}')
    with Image.open(io.BytesIO(preview.content)) as normalized:
        assert normalized.format == 'JPEG' and normalized.mode == 'RGB'
        assert normalized.size == (10, 20)
    assert client.delete(f'/api/sessions/{session}/images/{image["id"]}').json()['images'] == []


def test_invalid_image_and_origin(client):
    session = new(client)
    response = client.post(f'/api/sessions/{session}/images', files={'file': ('bad.png', b'not image')})
    assert response.status_code == 422
    assert client.get(f'/api/sessions/{session}').json()['images'] == []
    assert client.post('/api/sessions', headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client.post('/api/sessions', headers={'X-Identifier-Local': ''}).status_code == 403
    assert client.get('/api/health', headers={'Host': 'evil.example'}).status_code == 403


def test_evidence_continuity_and_isolation(client):
    a, b = new(client), new(client)
    image_a = upload(client, a).json()['images'][0]['id']
    result_a = run(client, a)
    assert result_a['result']['status'] == 'Needs Evidence'
    assert client.delete(f'/api/sessions/{a}/images/{image_a}').status_code == 409
    upload(client, b)
    run(client, b)
    upload(client, a, 'WEBP')
    FakeLangflow.output = RESOLVED
    followup = run(client, a, {'known': {'brand': "Levi's"}})
    assert followup['result']['status'] == 'Resolved'
    assert len(followup['images']) == 2
    assert len(FakeLangflow.calls[2][2]) == 1  # Only new images, verified M1 history handles old ones.
    assert FakeLangflow.calls[0][0] == FakeLangflow.calls[2][0] != FakeLangflow.calls[1][0]
    assert client.get(f'/api/sessions/{b}/images/{image_a}').status_code == 404
    assert len(client.get(f'/api/sessions/{b}').json()['attempts']) == 1


def test_manual_followup_no_more_and_general_acceptance(client):
    session = new(client)
    upload(client, session)
    run(client, session)
    run(client, session, {'known': {'brand': 'Goodfellow & Co.'}})
    assert FakeLangflow.calls[-1][2] == []
    assert 'Goodfellow & Co.' in FakeLangflow.calls[-1][1]
    FakeLangflow.output = UNRESOLVED
    result = run(client, session, {'no_more_information': True})
    assert result['result']['candidate'] == 'Possible model AB-12'
    accepted = client.post(f'/api/sessions/{session}/decision', json={'action': 'accepted general identity'}).json()
    assert accepted['result']['status'] == 'Unresolved'
    assert accepted['decision']['identity']['name'] == 'Shoes'
    assert accepted['decision']['identity']['product_name'] is None
    assert len(FakeLangflow.calls) == 3


def test_correction_confirmation_rejection_without_model_call(client):
    session = new(client)
    upload(client, session)
    FakeLangflow.output = RESOLVED
    run(client, session)
    for action in ['confirmed', 'rejected']:
        response = client.post(f'/api/sessions/{session}/decision', json={'action': action})
        assert response.status_code == 200
    assert client.post(f'/api/sessions/{session}/decision', json={'action': 'confirmed'}).status_code == 422
    correction = {'name': "Levi's 511 Slim Jeans", 'brand': "Levi's", 'product_name': '511 Slim', 'item_type': 'Jeans'}
    corrected = client.post(f'/api/sessions/{session}/decision', json={'action': 'corrected', 'identity': correction}).json()
    assert corrected['decision']['identity']['product_name'] == '511 Slim'
    assert corrected['result']['product_name'] == '511'
    assert len(FakeLangflow.calls) == 1
    repeated = run(client, session, {'known': {'other_information': 'New label evidence'}})
    assert 'The user rejected' in FakeLangflow.calls[-1][1]
    assert repeated['decision']['action'] == 'rejected'


@pytest.mark.parametrize('malformed', [False, True])
def test_operational_errors_fail_closed(client, malformed):
    session = new(client)
    upload(client, session)
    FakeLangflow.fail = not malformed
    FakeLangflow.output = 'Something went wrong. SECRET'
    result = run(client, session)
    assert result['execution_state'] == 'failed'
    assert result['result'] is None
    assert 'SECRET' not in result['error']
    assert client.post(f'/api/sessions/{session}/identify', json={'known': {'brand': 'retry'}}).status_code == 409
    assert not main.ENGINE_LOCK.locked()


def test_busy_rejects_without_changing_session(client):
    session = new(client)
    upload(client, session)
    main.ENGINE_LOCK.acquire()
    try:
        assert client.post(f'/api/sessions/{session}/identify', json={}).status_code == 409
        assert client.get(f'/api/sessions/{session}').json()['attempts'] == []
    finally: main.ENGINE_LOCK.release()


def test_restart_retains_data_and_fails_inflight(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DATA', tmp_path)
    with TestClient(main.app, headers={'X-Identifier-Local': '1'}) as c:
        session = new(c)
        stored = main.read(session)
        stored.update(execution_state='processing', attempts=[{'number': 1}])
        main.save(stored)
    with TestClient(main.app) as c:
        result = c.get(f'/api/sessions/{session}').json()
        assert result['execution_state'] == 'failed' and result['result'] is None


def test_credential_redaction():
    client = LangflowClient()
    client.secrets = ['private-api-key', 'private-cookie']
    assert client.redact('private-api-key private-cookie Bearer secret-token') == '[REDACTED] [REDACTED] Bearer [REDACTED]'


def test_envelope_session_mismatch():
    with pytest.raises(ValueError): extract_final({'session_id': 'other'}, 'requested')


TAYION = '''Status: Resolved
Name: Tayion Collection MADNCD008SLS Slim Fit Button Down Dress Shirt
Brand: Tayion Collection
Product Name: MADNCD008SLS
Style Accent: Yellow-Trimmed
Item Type: Shirt
Evidence: User supplied an identifier; black shirt with gold trim.
Sources: User evidence
'''


@pytest.mark.parametrize('label,code', [
    ('MPN', 'MADNCD008SLS'), ('UPC', '012345678905'), ('SKU', 'SHIRT-001'),
    ('barcode', '0012345678905'), ('EAN', '1234567890123'),
    ('GTIN', '00012345678905'), ('ASIN', 'B012345678'), ('part number', 'AB-12'),
])
def test_identifier_product_is_unknown_and_evidence_is_unchanged(client, label, code):
    session = new(client)
    FakeLangflow.output = TAYION.replace('MADNCD008SLS', code)
    supplied = {'identifiers': f'{label}: {code}'}
    state = run(client, session, {'known': supplied})
    result = state['result']
    assert state['execution_state'] == 'completed'
    assert result['status'] == 'Needs Evidence'
    assert result['product_name'] is None and result['style_accent'] is None
    assert result['name'] == 'Tayion Collection Shirt'
    assert result['missing_evidence'] and result['next_action']
    assert state['attempts'][0]['input']['known']['identifiers'] == supplied['identifiers']
    assert supplied['identifiers'] in FakeLangflow.calls[-1][1]
    assert state['attempts'][0]['raw_final'] == FakeLangflow.output
    assert state['attempts'][0]['parsed_result']['product_name'] == code
    assert result['evidence'] == parse_final(FakeLangflow.output).evidence
    assert client.post(f'/api/sessions/{session}/decision', json={'action': 'confirmed'}).status_code == 422


def test_tayion_followup_general_acceptance_and_identifier_continuity(client):
    session = new(client)
    run(client, session, {'known': {'identifiers': 'MPN: MADNCD008SLS'}})
    FakeLangflow.output = TAYION
    state = run(client, session, {'known': {'other_information': 'Black shirt with gold trim'}})
    assert state['result']['status'] == 'Unresolved'
    assert state['result']['product_name'] is None
    accepted = client.post(f'/api/sessions/{session}/decision', json={'action': 'accepted general identity'})
    assert accepted.status_code == 200
    assert accepted.json()['decision']['identity']['name'] == 'Tayion Collection Shirt'
    assert accepted.json()['decision']['identity']['product_name'] is None
    assert len(FakeLangflow.calls) == 2
    # Evidence belongs to this item, not every item in the application.
    other = run(client, new(client), {'known': {'brand': 'Tayion Collection'}})
    assert other['result']['product_name'] == 'MADNCD008SLS'


@pytest.mark.parametrize('supplied,rendered', [
    ('MADNCD008SLS', 'madncd008sls'),
    ('MPN: MADNCD008SLS; SKU: AB-12', 'MADNCD008SLS (SKU: AB-12)'),
    ('UPC: 0 12345 67890 5', '012345678905'),
    ('012345678905', '0 12345 67890 5'),
    ('AB-12', 'AB12'),
    ('ABC, DEF', 'ABC / DEF'),
])
def test_codes_removed_from_name_with_valid_product_name(client, supplied, rendered):
    session = new(client)
    FakeLangflow.output = TAYION.replace('Product Name: MADNCD008SLS', 'Product Name: Signature')
    FakeLangflow.output = FakeLangflow.output.replace('MADNCD008SLS', rendered)
    state = run(client, session, {'known': {'identifiers': supplied}})
    assert state['result']['status'] == 'Resolved'
    assert state['result']['product_name'] == 'Signature'
    assert state['result']['name'] == 'Tayion Collection Slim Fit Button Down Dress Shirt'
    confirmed = client.post(f'/api/sessions/{session}/decision', json={'action': 'confirmed'}).json()
    assert confirmed['decision']['identity']['name'] == state['result']['name']


@pytest.mark.parametrize('brand,product,item_type', [
    ("Levi's", '511 Slim', 'Jeans'), ('Nike', 'Air Zoom Pegasus 40', 'Shoes'),
    ('Sony', 'PlayStation 5', 'Console'),
])
def test_marketed_numbers_survive_recognition_and_correction(client, brand, product, item_type):
    session = new(client)
    name = f'{brand} {product} {item_type}'
    FakeLangflow.output = f'Status: Resolved\nName: {name}\nBrand: {brand}\nProduct Name: {product}\nItem Type: {item_type}'
    state = run(client, session, {'known': {'identifiers': 'SKU: AB-12; UPC: 012345678905'}})
    assert state['result']['name'] == name
    assert state['result']['product_name'] == product
    identity = {key: state['result'][key] for key in ('name', 'brand', 'product_name', 'item_type')}
    identity['name'] += ' AB-12'
    corrected = client.post(f'/api/sessions/{session}/decision', json={'action': 'corrected', 'identity': identity})
    assert corrected.status_code == 200
    assert corrected.json()['decision']['identity']['name'] == name
    identity['product_name'] = 'ab-12'
    assert client.post(f'/api/sessions/{session}/decision', json={'action': 'corrected', 'identity': identity}).status_code == 422
    assert len(FakeLangflow.calls) == 1


@pytest.mark.parametrize('status', ['Needs Evidence', 'Unresolved'])
def test_identifier_product_cleared_in_nonresolved_results(client, status):
    session = new(client)
    FakeLangflow.output = TAYION.replace('Status: Resolved', f'Status: {status}')
    FakeLangflow.output += '\nMissing Evidence: Packaging\nNext Action: Add packaging\nReason Unresolved: Unknown name'
    state = run(client, session, {'known': {'other_information': 'MPN: MADNCD008SLS'}})
    assert state['result']['status'] == status
    assert state['result']['product_name'] is None
    assert state['result']['name'] == 'Tayion Collection Shirt'


def test_labeled_image_evidence_also_guards_name(client):
    session = new(client)
    FakeLangflow.output = TAYION.replace('User supplied an identifier', 'Label shows MPN: MADNCD008SLS')
    upload(client, session)
    state = run(client, session)
    assert state['result']['product_name'] is None
    assert 'MPN: MADNCD008SLS' in state['result']['evidence']


def test_saved_legacy_identity_is_guarded_without_rewriting_history(client):
    session = new(client)
    run(client, session, {'known': {'identifiers': 'MPN: MADNCD008SLS'}})
    path = main.folder(session) / 'session.json'
    stored = json.loads(path.read_text())
    stored['result'] = parse_final(TAYION).model_dump()
    stored['attempts'][-1].update(raw_final=TAYION, parsed_result=stored['result'])
    stored['decision'] = {'action': 'corrected', 'identity': stored['result']}
    stored['decisions'] = [stored['decision']]
    main.save(stored)
    before = path.read_bytes()
    state = client.get(f'/api/sessions/{session}').json()
    assert state['result']['product_name'] is None
    assert state['decision'] is None
    assert state['decisions'] == stored['decisions']
    assert state['attempts'] == stored['attempts']
    assert path.read_bytes() == before


def test_numeric_identifier_does_not_remove_digits_inside_marketed_name(client):
    session = new(client)
    FakeLangflow.output = RESOLVED
    state = run(client, session, {'known': {'identifiers': 'SKU: 5'}})
    assert state['result']['status'] == 'Resolved'
    assert state['result']['product_name'] == '511'
    assert state['result']['name'] == parse_final(RESOLVED).name


def test_identifier_only_name_cannot_be_confirmed(client):
    session = new(client)
    FakeLangflow.output = TAYION.replace('Product Name: MADNCD008SLS', 'Product Name: Signature')
    FakeLangflow.output = FakeLangflow.output.replace(
        'Name: Tayion Collection MADNCD008SLS Slim Fit Button Down Dress Shirt', 'Name: MADNCD008SLS')
    state = run(client, session, {'known': {'identifiers': 'MPN: MADNCD008SLS'}})
    assert state['result']['name'] is None
    assert state['result']['status'] == 'Needs Evidence'
    assert client.post(f'/api/sessions/{session}/decision', json={'action': 'confirmed'}).status_code == 422


def test_exhausted_guarded_result_allows_general_identity(client):
    session = new(client)
    FakeLangflow.output = TAYION
    run(client, session, {'known': {'identifiers': 'MPN: MADNCD008SLS'}})
    state = run(client, session, {'no_more_information': True})
    assert state['result']['status'] == 'Unresolved'
    assert state['result']['product_name'] is None
    assert client.post(f'/api/sessions/{session}/decision', json={'action': 'accepted general identity'}).status_code == 200
