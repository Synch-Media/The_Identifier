"""Application naming rules; evidence and original recognition output stay intact."""
import re

from .parser import known


# The existing input combines model/style text and catalog codes. Only explicitly
# labeled codes or bare values in that input are identifiers, not arbitrary digits.
LABEL = (r'(?:UPC(?:-A|-E)?|MPN|SKU|bar\s*code|EAN(?:-13|-8)?|GTIN(?:-\d+)?|'
         r'ISBN(?:-13|-10)?|ASIN|(?:manufacturer\s+)?part\s*(?:number|no\.?|#)|'
         r'(?:model|style|catalog|catalogue|item)\s*(?:number|no\.?|#))')
LABELED = re.compile(r'\b' + LABEL + r'\s*(?::|=|#|\bis\b)?\s*[\"\'`]?'
                     r'(\d+(?:[ -]+\d+)+(?![A-Za-z0-9])|[A-Za-z0-9]+(?:[-./_][A-Za-z0-9]+)*)', re.I)


def identifiers_for(session):
    values = set()
    for attempt in session['attempts']:
        supplied = attempt.get('input', {}).get('known', {})
        for text in supplied.values():
            values.update(match[1] for match in LABELED.finditer(text or ''))
        # Multiple unlabeled codes may be separated by commas or semicolons.
        # Labeled values have already been collected above.
        bare = LABELED.sub('', supplied.get('identifiers', ''))
        for part in re.split(r'[,;\n]+', bare):
            part = part.strip(' \t\r\"\'`')
            if re.fullmatch(r'[A-Za-z0-9]+(?:[-./_][A-Za-z0-9]+)*|\d+(?: +\d+)+', part):
                values.add(part)
        parsed = attempt.get('parsed_result') or {}
        # Explicit labels in model evidence can also establish a known code
        # (for example, a barcode read from an image). Never infer one by shape.
        values.update(match[1] for match in LABELED.finditer(parsed.get('evidence', '')))
    return values


def without_identifiers(text, identifiers):
    if not text:
        return text
    original = text
    for value in sorted(identifiers, key=len, reverse=True):
        # Case, barcode grouping, and code separators do not change identity.
        code = r'[\s./_-]*'.join(re.escape(char) for char in value if char.isalnum())
        pattern = r'(?<![\w])(?:' + LABEL + r'\s*[:=#]?\s*)?' + code + r'(?![\w])'
        text = re.sub(pattern, '', text, flags=re.I)
    if text == original:
        return text
    text = re.sub(r'\(\s*\)|\[\s*\]', '', text)
    text = re.sub(r'\s+[/,;|]+\s+', ' ', text)
    return known(re.sub(r'\s+', ' ', text).strip(' \t\r\n,;:/-'))


def guard_identity(identity, identifiers):
    result = dict(identity)
    product = result.get('product_name')
    # Do not promote a leftover descriptive fragment to a marketed Product Name.
    if without_identifiers(product, identifiers) != product:
        result['product_name'] = None
    for field in ('brand', 'item_type', 'style_accent', 'name'):
        result[field] = without_identifiers(result.get(field), identifiers)
    if product and not result['product_name']:
        result['style_accent'] = None
        result['name'] = ' '.join(value for value in (result['brand'], result['item_type']) if value) or None
    return result


def guard_session(session):
    """Guard active state, including older saved items, without rewriting history."""
    identifiers = identifiers_for(session)
    if not identifiers:
        return session
    if session.get('result'):
        original = session['result']
        result = guard_identity(original, identifiers)
        if original['status'] == 'Resolved' and not all(result.get(field) for field in
                                                      ('name', 'brand', 'product_name', 'item_type')):
            previous_request = any((attempt.get('parsed_result') or {}).get('status') == 'Needs Evidence'
                                   for attempt in session['attempts'][:-1])
            exhausted = session['attempts'][-1].get('input', {}).get('no_more_information', False)
            explanation = 'A machine/catalog identifier is evidence, not a marketed Product Name.'
            if previous_request or exhausted:
                result.update(status='Unresolved', reason_unresolved=explanation)
            else:
                result.update(status='Needs Evidence', missing_evidence=explanation,
                              next_action='Add a label or packaging photo showing the marketed product name, or enter it manually.')
        session['result'] = result
    decision = session.get('decision')
    if decision:
        identity = guard_identity(decision['identity'], identifiers)
        if decision['action'] in {'confirmed', 'corrected'} and not all(identity.get(field) for field in
                                                                      ('name', 'brand', 'product_name', 'item_type')):
            session['decision'] = None
        else:
            session['decision'] = {**decision, 'identity': identity}
    return session
