import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { api } from './api'
import type { Decision, Identity, Known, Result, Session } from './types'
import './style.css'

const emptyKnown: Known = { brand: '', product_name: '', identifiers: '', item_type: '', other_information: '' }
const identityLabels: [keyof Identity, string][] = [['name', 'Name'], ['brand', 'Brand'], ['product_name', 'Product Name'], ['style_accent', 'Style Accent'], ['item_type', 'Item Type']]
const infoLabels: [keyof Known, string][] = [['brand', 'Brand'], ['product_name', 'Product Name'], ['identifiers', 'Model / Style / SKU / UPC'], ['item_type', 'Item Type'], ['other_information', 'Other Information']]

function Sources({ text }: { text: string }) {
  // Link only explicit http(s) URLs; model output is always rendered as text.
  return <p className="multiline sources">{text.split(/(https?:\/\/[^\s<>"\]]+)/g).map((part, i) => /^https?:\/\//.test(part) ? <a key={i} href={part.replace(/[).,;]+$/, '')} target="_blank" rel="noopener noreferrer">{part}</a> : part)}</p>
}

function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [known, setKnown] = useState<Known>({ ...emptyKnown })
  const [error, setError] = useState('')
  const [working, setWorking] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [editing, setEditing] = useState<Identity | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const input = useRef<HTMLInputElement>(null)
  const info = useRef<HTMLDetailsElement>(null)
  const activeId = useRef<string | null>(null)
  const booted = useRef(false)
  const processing = session?.execution_state === 'processing'
  const disabled = working || processing
  const failed = session?.execution_state === 'failed'
  const result = session?.result
  const decision = session?.decision
  const rejected = decision?.action === 'rejected'
  const accepted = decision && !rejected
  const latest = session?.attempts.at(-1)
  const canRun = session?.images.some(image => !image.submitted) || Object.values(known).some(value => value.trim())

  function receive(value: Session) { activeId.current = value.id; setSession(value); sessionStorage.setItem('identifierSession', value.id) }

  async function newItem() {
    setWorking(true); setError('')
    try { receive(await api<Session>('/sessions', 'POST')); setKnown({ ...emptyKnown }); setEditing(null); setExpanded(false) }
    catch (e) { setError(message(e)) }
    finally { setWorking(false) }
  }

  useEffect(() => {
    if (booted.current) return
    booted.current = true
    const id = sessionStorage.getItem('identifierSession')
    if (id) api<Session>(`/sessions/${id}`).then(receive).catch(() => setError('Could not restore this item. Check the backend, then reload or start a new item.'))
    else void newItem()
  }, [])

  useEffect(() => {
    if (!processing || !session) return
    const id = session.id
    let stopped = false
    let timeout: ReturnType<typeof setTimeout>
    async function poll() {
      try {
        const value = await api<Session>(`/sessions/${id}`)
        if (!stopped && activeId.current === id) { setSession(value); setError('') }
      } catch { if (!stopped) setError('Connection interrupted. Reconnecting to this item; do not resubmit.') }
      if (!stopped) timeout = setTimeout(poll, 1500)
    }
    timeout = setTimeout(poll, 1000)
    const tick = setInterval(() => setElapsed(Math.max(0, Math.floor((Date.now() - Date.parse(session.attempts.at(-1)!.started_at)) / 1000))), 1000)
    return () => { stopped = true; clearTimeout(timeout); clearInterval(tick) }
  }, [processing, session?.id])

  function message(e: unknown) { return e instanceof Error ? e.message : 'The request could not be completed.' }

  async function photos(files: FileList | File[]) {
    if (!session || disabled || failed) return
    setWorking(true); setError('')
    try {
      for (const file of Array.from(files)) {
        if (!/\.(jpe?g|png|webp)$/i.test(file.name)) throw new Error('Choose JPG, PNG, or WebP files.')
        const form = new FormData(); form.append('file', file)
        receive(await api<Session>(`/sessions/${session.id}/images`, 'POST', form))
      }
    } catch (e) { setError(message(e)) }
    finally { setWorking(false); if (input.current) input.current.value = '' }
  }

  async function remove(id: string) {
    if (!session) return
    setWorking(true); setError('')
    try { receive(await api<Session>(`/sessions/${session.id}/images/${id}`, 'DELETE')) }
    catch (e) { setError(message(e)) }
    finally { setWorking(false) }
  }

  async function identify(noMore = false) {
    if (!session) return
    setWorking(true); setError(''); setElapsed(0)
    try {
      receive(await api<Session>(`/sessions/${session.id}/identify`, 'POST', { known, no_more_information: noMore }))
      setKnown({ ...emptyKnown }); setEditing(null)
    } catch (e) { setError(message(e)) }
    finally { setWorking(false) }
  }

  async function decide(action: Decision['action'], identity?: Identity) {
    if (!session) return
    setWorking(true); setError('')
    try { receive(await api<Session>(`/sessions/${session.id}/decision`, 'POST', { action, identity })); setEditing(null) }
    catch (e) { setError(message(e)) }
    finally { setWorking(false) }
  }

  function showInfo() { setExpanded(true); setTimeout(() => { info.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }); info.current?.querySelector('input')?.focus() }, 0) }
  function edit() {
    const current = accepted ? decision.identity : result!
    setEditing(Object.fromEntries(identityLabels.map(([key]) => [key, current[key] || ''])) as Identity)
  }

  function changeIdentity(key: keyof Identity, value: string) {
    if (!editing) return
    const next = { ...editing, [key]: value }
    if (key !== 'name') {
      const parts = [next.brand, next.product_name, next.style_accent].filter(Boolean)
      if (next.item_type && !parts.join(' ').toLowerCase().endsWith(next.item_type.toLowerCase())) parts.push(next.item_type)
      next.name = parts.join(' ')
    }
    setEditing(next)
  }

  const identity = accepted ? decision.identity : result
  return <>
    <header><div className="brand"><span className="brandmark" aria-hidden="true">i</span>Identifier</div><span className="local"><span/> LOCAL WORKSPACE</span></header>
    <main>
      <div className="intro"><div><p className="eyebrow">A LITTLE EVIDENCE. A CLEARER IDENTITY.</p><h1>Know your item.</h1><p>Add a photo. Share what you know. Find the most specific identity the evidence supports.</p></div><button className="quiet" disabled={disabled} onClick={newItem}>Start New Item <span aria-hidden="true">↗</span></button></div>
      {error && <div role="alert" className="error">{error}</div>}
      <div className="workspace">
        <section className="card evidence-card" aria-labelledby="evidence-title">
          <div className="section-title"><span className="step">01</span><h2 id="evidence-title">Your evidence</h2><span className="muted">{session?.images.length || 0} / 8 photos</span></div>
          <input ref={input} className="sr-only" aria-label="Choose product photos" type="file" multiple accept=".jpg,.jpeg,.png,.webp" disabled={disabled || failed || !session} onChange={e => e.target.files && photos(e.target.files)}/>
          <div className={`dropzone ${dragging ? 'dragging' : ''}`} onDragOver={e => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={e => { e.preventDefault(); setDragging(false); void photos(e.dataTransfer.files) }}>
            <svg aria-hidden="true" width="38" height="38" viewBox="0 0 32 32" fill="none"><rect x="4" y="5" width="24" height="22" rx="5" stroke="currentColor" strokeWidth="1.5"/><circle cx="12" cy="12" r="2.5" stroke="currentColor" strokeWidth="1.5"/><path d="m5 23 7-6 5 4 5-7 5 7" stroke="currentColor" strokeWidth="1.5"/></svg>
            <h3>Drop your item photos here</h3><p>A clear overview is a good place to start.</p>
            <button disabled={disabled || failed || !session} onClick={() => input.current?.click()}>Choose Photos</button><small>JPG, PNG or WebP · up to 20 MB each</small>
          </div>
          {!!session?.images.length && <div className="photos">{session.images.map((image, i) => <figure key={image.id}><img src={`/api/sessions/${session.id}/images/${image.id}`} alt={`Item evidence ${i + 1}: ${image.filename}`}/><figcaption title={image.filename}>{image.filename}</figcaption>{image.submitted ? <small>Retained evidence</small> : <button className="remove" disabled={disabled} onClick={() => remove(image.id)} aria-label={`Remove ${image.filename}`}>×</button>}</figure>)}</div>}
          {session?.images.some(image => image.submitted) && <p className="hint">Submitted photos stay with this item for follow-up. Start a new item to leave them behind.</p>}
          <details ref={info} open={expanded} onToggle={e => setExpanded(e.currentTarget.open)} className="known"><summary>Add What I Know <span>Optional</span></summary><div className="fields">{infoLabels.map(([key, label]) => <label key={key}>{label}{key === 'other_information' ? <textarea maxLength={3000} value={known[key]} disabled={disabled || failed} onChange={e => setKnown({ ...known, [key]: e.target.value })}/> : <input maxLength={key === 'identifiers' ? 500 : 300} value={known[key]} disabled={disabled || failed} onChange={e => setKnown({ ...known, [key]: e.target.value })}/>}</label>)}</div></details>
          <button className="primary identify" disabled={!session || disabled || failed || !canRun} onClick={() => identify()}>{processing ? 'Analyzing item…' : session?.attempts.length ? 'Identify with Added Evidence' : 'Identify'}<span aria-hidden="true">→</span></button>
          <p className="hint center">Each new item has its own evidence and conversation.</p>
        </section>
        <section className="card result-card" aria-labelledby="result-title">
          <div className="section-title"><span className="step">02</span><h2 id="result-title">Identification</h2></div>
          {!result && !processing && !failed && <div className="empty"><div className="outline-icon" aria-hidden="true">⌕</div><h3>Every detail is a clue.</h3><p>Your result will appear here, along with the evidence behind it and a clear next step.</p><div className="state-guide"><span>Resolved</span><span>Needs Evidence</span><span>Unresolved</span></div></div>}
          {processing && <div className="empty" role="status"><div className="spinner"/><h3>Analyzing item…</h3><p>Identifier is reviewing your evidence. This may take a few minutes.</p><p className="muted">{elapsed}s elapsed</p></div>}
          {failed && <div role="alert" className="failure"><span className="badge">Execution failed</span><h3>Identification could not finish.</h3><p>{session?.error}</p><p>Your evidence is retained. This is an operational error, not an Unresolved result.</p><button onClick={newItem} disabled={disabled}>Start New Item</button></div>}
          {result && <div className="result-content">
            <div className="result-heading"><span className={`badge ${result.status === 'Resolved' && !rejected ? 'green' : 'amber'}`}>{rejected ? 'Rejected by you' : result.status}</span>{accepted && <span className="decision">{decision.action === 'accepted general identity' ? 'General identity accepted' : decision.action === 'corrected' ? 'Corrected by you' : 'Confirmed by you'}</span>}</div>
            <h3 className="item-name">{rejected ? 'Let’s take another look.' : identity?.name || 'What Identifier currently knows'}</h3>
            {accepted && result.status !== 'Resolved' && <p className="hint">Your saved identity is shown below. The original recognition outcome remains {result.status}.</p>}
            {rejected ? <p>The proposed identity was rejected. Add a photo or information to reassess this same item, or enter a correction.</p> : <dl className="identity">{identityLabels.filter(([key]) => key !== 'name' && (key !== 'style_accent' || identity?.[key])).map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{identity?.[key] || 'Unknown'}</dd></div>)}</dl>}
            {!rejected && result.candidate && <div className="candidate"><h4>Candidate · unconfirmed</h4><p>{result.candidate}</p></div>}
            {([['Important evidence', result.evidence], ['Missing Evidence', result.missing_evidence], ['Next Action', result.next_action], ['Reason Unresolved', result.reason_unresolved], ['Optional detail', result.missing_optional_information]] as const).map(([label, content]) => content && <div className="result-block" key={label}><h4>{label}</h4><p className="multiline">{content}</p></div>)}
            {result.sources && <div className="result-block"><h4>Sources</h4><Sources text={result.sources}/></div>}
            {result.status === 'Unresolved' && session!.attempts.length > 1 && <details className="earlier-evidence"><summary>Earlier evidence for this item</summary><p className="hint">Earlier observations and candidates are retained here for comparison; candidates remain unconfirmed.</p>{session!.attempts.slice(0, -1).map(attempt => <div className="result-block" key={attempt.number}><h4>Attempt {attempt.number}</h4>{attempt.parsed_result?.candidate && <p>Candidate: {attempt.parsed_result.candidate}</p>}<p className="multiline">{attempt.parsed_result?.evidence}</p>{Object.entries(attempt.input.known).filter(([, value]) => value).map(([key, value]) => <p key={key}>You supplied {infoLabels.find(([field]) => field === key)?.[1]}: {value}</p>)}</div>)}</details>}
            {!editing && <div className="actions">
              {result.status === 'Resolved' && !rejected && !accepted && <button className="primary" disabled={disabled} onClick={() => decide('confirmed')}>Looks Right</button>}
              {result.status === 'Resolved' && <button disabled={disabled} onClick={edit}>Edit</button>}
              {result.status === 'Resolved' && !rejected && !accepted && <button className="quiet" disabled={disabled} onClick={() => decide('rejected')}>Not This Item</button>}
              {(result.status === 'Needs Evidence' || rejected) && <button disabled={disabled} onClick={() => input.current?.click()}>Add Another Photo</button>}
              {result.status !== 'Resolved' && !accepted && <button disabled={disabled} onClick={showInfo}>Enter Information Manually</button>}
              {result.status === 'Needs Evidence' && !accepted && <button className="quiet" disabled={disabled} onClick={() => identify(true)}>I Don't Have More Information</button>}
              {result.status === 'Unresolved' && !accepted && result.item_type && !result.product_name && <button className="primary" disabled={disabled} onClick={() => decide('accepted general identity')}>Accept General Identity</button>}
            </div>}
            {result.status === 'Unresolved' && !accepted && result.item_type && !result.product_name && <p className="hint">General identity: {[result.brand, result.item_type].filter(Boolean).join(' ')}. No exact product name will be added.</p>}
            {editing && <form className="edit-form" onSubmit={e => { e.preventDefault(); void decide('corrected', editing) }}><h4>Correct this identification</h4><p className="hint">Saved as your correction. No new model call. Field changes update Name; you can also edit it directly.</p><div className="fields">{identityLabels.map(([key, label]) => <label key={key}>{label}{key === 'style_accent' ? ' (optional)' : ''}<input required={key !== 'style_accent'} maxLength={key === 'name' ? 500 : 300} value={editing[key] || ''} onChange={e => changeIdentity(key, e.target.value)}/></label>)}</div><div className="actions"><button className="primary" disabled={disabled} type="submit">Save Correction</button><button type="button" disabled={disabled} onClick={() => setEditing(null)}>Cancel</button></div></form>}
          </div>}
        </section>
      </div>
      {session && <details className="debug"><summary>Debug / Technical Details</summary><dl><dt>Identifier session ID</dt><dd>{session.id}</dd><dt>Langflow session ID</dt><dd>{session.langflow_session_id}</dd><dt>Execution state</dt><dd>{session.execution_state}</dd><dt>Attempt number</dt><dd>{session.attempts.length}</dd><dt>Runtime</dt><dd>{latest?.runtime_seconds != null ? `${latest.runtime_seconds}s` : processing ? `${elapsed}s (running)` : '—'}</dd></dl><h4>Raw final Langflow Agent output</h4><pre>{latest?.raw_final || 'No final output yet.'}</pre><h4>Parsed application result</h4><pre>{JSON.stringify(result, null, 2)}</pre><h4>User decision</h4><pre>{JSON.stringify(decision, null, 2)}</pre><h4>Operational errors</h4><pre>{[session.error, latest?.cleanup_warning].filter(Boolean).join('\n') || 'None'}</pre>{session.attempts.length > 1 && <details><summary>Earlier attempts and supplied information</summary><pre>{JSON.stringify(session.attempts, null, 2)}</pre></details>}</details>}
      <footer><span>Identifier / First Usable App</span><span>Evidence first. You make the final call.</span></footer>
    </main>
  </>
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>)
