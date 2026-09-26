"""Milestone 1's verified local cookie + temporary API-key recipe, backend only."""
import http.cookiejar
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener

from scripts.integration_probe import NoRedirect
from scripts.integration_run import BASE, FLOW, INPUT, OUTPUT, extract_final


class LangflowClient:
    def __init__(self):
        self.cookies = http.cookiejar.CookieJar()
        self.opener = build_opener(ProxyHandler({}), NoRedirect(), HTTPCookieProcessor(self.cookies))
        self.secret = None
        self.key_id = None
        self.secrets = []
        self.cleanup_warning = None

    def call(self, path, payload=None, headers=None, method=None, timeout=30):
        headers = dict(headers or {})
        if self.secret:
            headers['x-api-key'] = self.secret
        if isinstance(payload, dict):
            payload = json.dumps(payload).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        with self.opener.open(Request(BASE + path, data=payload, headers=headers, method=method), timeout=timeout) as response:
            return json.load(response)

    def authenticate(self):
        token = self.call('/api/v1/auto_login')
        self.secrets.extend(v for k, v in token.items() if isinstance(v, str) and ('token' in k or 'key' in k))
        self.secrets.extend(cookie.value for cookie in self.cookies)
        key = self.call('/api/v1/api_key/', {
            'name': 'Identifier M2 temporary ' + uuid.uuid4().hex[:8],
            'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        })
        self.key_id, self.secret = key['id'], key['api_key']
        self.secrets.append(self.secret)

    def upload(self, path):
        boundary = 'identifier-' + uuid.uuid4().hex
        filename = 'identifier-m2-' + uuid.uuid4().hex + '.jpg'
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                'Content-Type: image/jpeg\r\n\r\n').encode() + path.read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
        result = self.call('/api/v1/files/upload/' + FLOW, body,
                           {'Content-Type': 'multipart/form-data; boundary=' + boundary})
        reference = result.get('file_path')
        if not isinstance(reference, str) or not reference.startswith(FLOW + '/'):
            raise ValueError('Unexpected Langflow upload response')
        return reference

    def run(self, session, text, files):
        payload = {'input_request': {
            'input_value': text, 'input_type': 'chat', 'output_type': 'chat',
            'output_component': OUTPUT, 'session_id': session,
            'tweaks': {INPUT: {'files': files}},
        }}
        response = self.call('/api/v1/run/' + FLOW + '?stream=false', payload, timeout=420)
        return self.redact(extract_final(response, session))

    def redact(self, text):
        for secret in sorted(set(self.secrets), key=len, reverse=True):
            if secret:
                text = text.replace(secret, '[REDACTED]')
        text = re.sub(r'(?i)(bearer\s+)[\w.\-]+', r'\1[REDACTED]', text)
        return text

    def close(self):
        if self.key_id:
            try:
                self.call('/api/v1/api_key/' + self.key_id, method='DELETE')
            except Exception:
                self.cleanup_warning = 'Temporary Langflow key cleanup failed. The key expires within one hour.'
        self.secret = None
