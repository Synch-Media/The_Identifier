"""Parse final labeled output only. Malformed output is an execution failure."""
import re

from .models import Recognition

LABELS = {
    'Status': 'status', 'Name': 'name', 'Brand': 'brand',
    'Product Name': 'product_name', 'Style Accent': 'style_accent',
    'Item Type': 'item_type', 'Candidate': 'candidate', 'Evidence': 'evidence',
    'Missing Evidence': 'missing_evidence', 'Next Action': 'next_action',
    'Reason Unresolved': 'reason_unresolved', 'Sources': 'sources',
    'Missing Optional Information': 'missing_optional_information',
}
HEADER = re.compile(r'^(' + '|'.join(LABELS) + r')\s*:\s*(.*)$', re.I)
UNKNOWN = {'', 'unknown', 'none', 'n/a', 'not known', 'not identified', 'unresolved', 'not provided'}


def known(value):
    if not value:
        return None
    clean = value.strip().lower().rstrip('.')
    if clean in UNKNOWN or re.match(r'^(unknown|unresolved|not identified|not known)\b', clean):
        return None
    return value


def parse_final(text: str) -> Recognition:
    fields = {}
    current = None
    lookup = {label.lower(): key for label, key in LABELS.items()}
    for original in text.splitlines():
        line = original.strip()
        # Tolerate Markdown headings/bold labels without interpreting HTML or links.
        clean = re.sub(r'^#{1,6}\s+', '', line).replace('**', '')
        match = HEADER.match(clean)
        if match:
            current = lookup[match[1].lower()]
            if current in fields:
                raise ValueError('Duplicate final-output field: ' + current)
            fields[current] = match[2].strip()
        elif current:
            fields[current] += '\n' + line
        elif line:
            raise ValueError('Unexpected text before final-output fields')
    fields = {key: value.strip() for key, value in fields.items()}
    for key in ('name', 'brand', 'product_name', 'style_accent', 'item_type', 'candidate'):
        fields[key] = known(fields.get(key))
    result = Recognition.model_validate(fields)
    if result.status == 'Resolved' and not all((result.name, result.brand, result.product_name, result.item_type)):
        raise ValueError('Resolved output is missing a required identity field')
    if result.style_accent and not (result.brand and result.product_name):
        raise ValueError('Style Accent is unsupported without Brand and Product Name')
    if result.status == 'Needs Evidence' and not (result.missing_evidence and result.next_action):
        raise ValueError('Needs Evidence output is missing its evidence request or next action')
    return result
