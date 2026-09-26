"""Read-only Milestone 1 probe. No flow executions, uploads, or configuration changes.

Usage: python scripts/integration_probe.py --base-url http://127.0.0.1:7860
Evidence is written under data/integration/<UTC timestamp>/.
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    url = urlsplit(base)
    if (url.scheme != 'http' or url.hostname not in {'localhost', '127.0.0.1', '::1'}
            or url.username or url.password or url.query or url.fragment
            or url.path not in {'', '/'}):
        parser.error('Supply an HTTP loopback origin without credentials or a path.')

    root = Path(__file__).resolve().parents[1]
    now = datetime.now(timezone.utc)
    evidence = root / 'data' / 'integration' / now.strftime('%Y%m%dT%H%M%S%fZ')
    evidence.mkdir(parents=True, exist_ok=False)
    export = Path(r'D:\LocalAI\Langflow\Exports\Identifier_LM Studio_Gamma.json')
    report = {
        'checked_at_utc': now.isoformat(),
        'base_url': base,
        'authentication': 'No credentials sent; availability probe only.',
        'export_sha256': hashlib.sha256(export.read_bytes()).hexdigest(),
        'checks': [],
    }
    opener = build_opener(ProxyHandler({}), NoRedirect())
    for path, filename in [('/api/v1/version', 'version.json'),
                           ('/openapi.json', 'openapi.json')]:
        check = {'method': 'GET', 'path': path}
        try:
            request = Request(base + path, headers={'Accept': 'application/json'})
            with opener.open(request, timeout=8) as response:
                check['http_status'] = response.status
                body = response.read()
                value = json.loads(body)
                (evidence / filename).write_text(
                    json.dumps(value, indent=2), encoding='utf-8')
                check['response_file'] = filename
        except HTTPError as exc:
            check.update(outcome='http_error', http_status=exc.code)
        except (URLError, TimeoutError, OSError) as exc:
            check.update(outcome='connection_error', detail=str(exc))
        except (ValueError, UnicodeError) as exc:
            check.update(outcome='invalid_json', detail=str(exc))
        report['checks'].append(check)
        print(json.dumps(check))
    (evidence / 'probe.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'Evidence: {evidence}')
    return 0 if all('response_file' in check for check in report['checks']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
