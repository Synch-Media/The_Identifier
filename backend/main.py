import io
import json
import threading
import time
import uuid
import warnings
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image, ImageOps, UnidentifiedImageError

from .langflow import LangflowClient
from .models import DecisionInput, Identity, RunInput
from .naming import guard_identity, guard_session, identifiers_for
from .parser import known, parse_final

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'sessions'
STORE_LOCK = threading.RLock()
ENGINE_LOCK = threading.Lock()
MAX_BYTES = 20 * 1024 * 1024
MAX_IMAGES = 8
Image.MAX_IMAGE_PIXELS = 25_000_000


def now():
    return datetime.now(timezone.utc).isoformat()


def folder(session_id):
    try:
        if str(uuid.UUID(session_id)) != session_id:
            raise ValueError()
    except ValueError:
        raise HTTPException(404, 'Item session not found')
    return DATA / session_id


def read(session_id):
    with STORE_LOCK:
        try:
            return guard_session(json.loads((folder(session_id) / 'session.json').read_text(encoding='utf-8')))
        except FileNotFoundError:
            raise HTTPException(404, 'Item session not found')


def save(session):
    with STORE_LOCK:
        destination = folder(session['id']) / 'session.json'
        temporary = destination.with_suffix('.tmp')
        temporary.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding='utf-8')
        temporary.replace(destination)


@asynccontextmanager
async def lifespan(app):
    DATA.mkdir(parents=True, exist_ok=True)
    for path in DATA.glob('*/session.json'):
        session = json.loads(path.read_text(encoding='utf-8'))
        if session['execution_state'] == 'processing':
            session['execution_state'] = 'failed'
            session['error'] = 'The backend stopped during recognition. Start a new item; the previous Langflow call may have continued.'
            session['attempts'][-1].update(error=session['error'], finished_at=now())
            save(session)
    yield


app = FastAPI(title='Identifier local application', lifespan=lifespan)


@app.middleware('http')
async def local_only(request: Request, call_next):
    host = request.headers.get('host', '').split(':')[0]
    origin = request.headers.get('origin')
    if host not in {'127.0.0.1', 'localhost', 'testserver'}:
        return JSONResponse({'detail': 'Only local requests are supported'}, status_code=403)
    if origin and origin not in {'http://127.0.0.1:5173', 'http://localhost:5173', 'http://127.0.0.1:8000', 'http://localhost:8000'}:
        return JSONResponse({'detail': 'Origin is not allowed'}, status_code=403)
    # Prevent other websites submitting local jobs, without introducing accounts.
    if request.method in {'POST', 'DELETE', 'PATCH'} and request.headers.get('x-identifier-local') != '1':
        return JSONResponse({'detail': 'Local application header required'}, status_code=403)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@app.get('/api/health')
def health():
    return {'status': 'ok', 'engine_busy': ENGINE_LOCK.locked()}


@app.post('/api/sessions', status_code=201)
def create_session():
    session_id = str(uuid.uuid4())
    folder(session_id).mkdir(parents=True)
    session = {'id': session_id, 'langflow_session_id': 'identifier-m2-' + session_id,
               'created_at': now(), 'execution_state': 'idle', 'images': [],
               'attempts': [], 'result': None, 'decision': None, 'decisions': [], 'error': None}
    save(session)
    return session


@app.get('/api/sessions/{session_id}')
def get_session(session_id: str):
    return read(session_id)


def editable(session):
    if session['execution_state'] == 'processing':
        raise HTTPException(409, 'Please wait for this identification to finish')
    if session['execution_state'] == 'failed':
        raise HTTPException(409, 'Start a new item after an execution failure to avoid ambiguous conversation history')


@app.post('/api/sessions/{session_id}/images', status_code=201)
def upload_image(session_id: str, file: UploadFile = File(...)):
    with STORE_LOCK:
        session = read(session_id)
        editable(session)
        if len(session['images']) >= MAX_IMAGES:
            raise HTTPException(422, 'Use at most 8 photos per item')
        raw = file.file.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise HTTPException(422, 'Each photo must be 20 MB or smaller')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as image:
                    if image.format not in {'JPEG', 'PNG', 'WEBP'}:
                        raise ValueError('Use a JPG, PNG, or WebP image')
                    if getattr(image, 'n_frames', 1) != 1:
                        raise ValueError('Animated images are not supported')
                    image.load()
                    rgba = ImageOps.exif_transpose(image).convert('RGBA')
                    canvas = Image.new('RGBA', rgba.size, 'white')
                    canvas.alpha_composite(rgba)
                    buffer = io.BytesIO()
                    canvas.convert('RGB').save(buffer, 'JPEG', quality=95, subsampling=0)
        except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise HTTPException(422, 'Use a valid, non-animated JPG, PNG, or WebP up to 25 megapixels')
        image_id = uuid.uuid4().hex
        directory = folder(session_id)
        (directory / (image_id + '.original')).write_bytes(raw)
        (directory / (image_id + '.jpg')).write_bytes(buffer.getvalue())
        session['images'].append({'id': image_id, 'filename': Path((file.filename or 'Photo').replace('\\', '/')).name[:200],
                                  'width': canvas.width, 'height': canvas.height, 'submitted': False})
        save(session)
        return session


@app.get('/api/sessions/{session_id}/images/{image_id}')
def preview(session_id: str, image_id: str):
    session = read(session_id)
    if not any(image['id'] == image_id for image in session['images']):
        raise HTTPException(404, 'Photo not found')
    return FileResponse(folder(session_id) / (image_id + '.jpg'), media_type='image/jpeg')


@app.delete('/api/sessions/{session_id}/images/{image_id}')
def remove_image(session_id: str, image_id: str):
    with STORE_LOCK:
        session = read(session_id)
        editable(session)
        image = next((image for image in session['images'] if image['id'] == image_id), None)
        if not image:
            raise HTTPException(404, 'Photo not found')
        if image['submitted']:
            raise HTTPException(409, 'This photo is already part of the evidence. Start a new item to exclude it.')
        session['images'].remove(image)
        save(session)
        for suffix in ('.original', '.jpg'):
            (folder(session_id) / (image_id + suffix)).unlink(missing_ok=True)
        return session


def prompt_for(session, request):
    if request.no_more_information:
        text = "I don't have any more information or photos for this same item. Reassess using the available evidence."
    elif session['attempts']:
        text = 'Additional evidence for the same item. Reassess using this evidence and the earlier images and information.'
    else:
        text = 'Identify this product according to the Identifier workflow.'
    supplied = {key: value for key, value in request.known.model_dump().items() if value}
    if supplied:
        text += '\nUser-provided information:\n' + json.dumps(supplied, ensure_ascii=False)
    rejected = [d['identity'] for d in session['decisions'] if d['action'] == 'rejected']
    if rejected:
        text += '\nThe user rejected these identifications for this item. Do not silently reuse them:\n' + json.dumps(rejected)
    return text


def execute(session_id, text, image_ids):
    started = time.monotonic()
    client = LangflowClient()
    result = None
    raw = None
    error = None
    try:
        session = read(session_id)
        client.authenticate()
        references = [client.upload(folder(session_id) / (image_id + '.jpg')) for image_id in image_ids]
        raw = client.run(session['langflow_session_id'], text, references)
        result = parse_final(raw).model_dump()
    except HTTPError as exc:
        error = f'Langflow returned HTTP {exc.code}. Check Langflow and LM Studio, then start a new item.'
    except (URLError, TimeoutError, OSError):
        error = 'Could not complete the local Langflow request. Check the local services. Start a new item; a timed-out request may still be running.'
    except (ValueError, KeyError, TypeError, AttributeError):
        error = 'The final Langflow output did not match the validated application contract. See the final output below; no recognition result was created.'
    except Exception:
        error = 'An unexpected execution error occurred. No recognition result was created.'
    finally:
        client.close()
        try:
            with STORE_LOCK:
                session = read(session_id)
                session['attempts'][-1].update(runtime_seconds=round(time.monotonic() - started, 2),
                    finished_at=now(), raw_final=raw, parsed_result=result, error=error,
                    cleanup_warning=client.cleanup_warning)
                session.update(execution_state='failed' if error else 'completed', error=error, result=result)
                guard_session(session)
                result = session['result']
                # A repeated rejected identity remains visibly rejected, even if the
                # model overlooks the user's rejection in the follow-up message.
                if result and result['status'] == 'Resolved':
                    keys = ('brand', 'product_name', 'item_type')
                    normalized = lambda item: tuple((item.get(key) or '').strip().casefold() for key in keys)
                    previous = next((d for d in reversed(session['decisions'])
                                     if d['action'] == 'rejected' and normalized(d['identity']) == normalized(result)), None)
                    if previous:
                        session['decision'] = previous
                save(session)
        finally:
            ENGINE_LOCK.release()


@app.post('/api/sessions/{session_id}/identify', status_code=202)
def identify(session_id: str, request: RunInput, tasks: BackgroundTasks):
    with STORE_LOCK:
        session = read(session_id)
        editable(session)
        image_ids = [image['id'] for image in session['images'] if not image['submitted']]
        if request.no_more_information and (not session['result'] or session['result']['status'] == 'Resolved'):
            raise HTTPException(422, 'An evidence request must precede this action')
        if not request.no_more_information and not image_ids and not any(request.known.model_dump().values()):
            raise HTTPException(422, 'Add a photo or enter information first')
        if len(session['attempts']) >= 12:
            raise HTTPException(422, 'This development session has reached 12 attempts. Start a new item.')
        if not ENGINE_LOCK.acquire(blocking=False):
            raise HTTPException(409, 'Another item is being analyzed. Please wait, then try again.')
        try:
            text = prompt_for(session, request)
            session.update(execution_state='processing', error=None, decision=None, result=None)
            session['attempts'].append({'number': len(session['attempts']) + 1, 'started_at': now(),
                'input': request.model_dump(), 'image_ids': image_ids, 'raw_final': None, 'parsed_result': None,
                'runtime_seconds': None, 'error': None})
            for image in session['images']:
                if image['id'] in image_ids:
                    image['submitted'] = True
            save(session)
            tasks.add_task(execute, session_id, text, image_ids)
        except Exception:
            ENGINE_LOCK.release()
            raise
        return session


@app.post('/api/sessions/{session_id}/decision')
def decide(session_id: str, request: DecisionInput):
    with STORE_LOCK:
        session = read(session_id)
        editable(session)
        result = session['result']
        if not result:
            raise HTTPException(422, 'An identification result is required first')
        if request.action in {'confirmed', 'rejected'}:
            if result['status'] != 'Resolved' or (session['decision'] and session['decision']['action'] == 'rejected'):
                raise HTTPException(422, 'This action requires a current Resolved result')
            identity = Identity.model_validate({key: result[key] for key in Identity.model_fields})
        elif request.action == 'corrected':
            identity = request.identity
            if identity:
                identity = Identity.model_validate(guard_identity(identity.model_dump(), identifiers_for(session)))
            if not identity or not all(known(v) for v in (identity.name, identity.brand, identity.product_name, identity.item_type)):
                raise HTTPException(422, 'Enter Name, Brand, a marketed Product Name (not a UPC, MPN, SKU, or barcode), and Item Type for a corrected identity')
        else:
            if result['status'] != 'Unresolved' or not known(result['item_type']) or result['product_name']:
                raise HTTPException(422, 'A supported general item type without an exact product name is required')
            identity = Identity(brand=result['brand'], item_type=result['item_type'],
                                name=' '.join(v for v in (result['brand'], result['item_type']) if v))
        identity = Identity.model_validate(guard_identity(identity.model_dump(), identifiers_for(session)))
        decision = {'action': request.action, 'identity': identity.model_dump(), 'at': now(),
                    'attempt_number': len(session['attempts'])}
        session['decision'] = decision
        session['decisions'].append(decision)
        save(session)
        return session
