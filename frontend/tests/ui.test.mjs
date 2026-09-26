import { test } from 'node:test'
import assert from 'node:assert/strict'
import { chromium } from '@playwright/test'

// Browser UI tests intercept only /api; they never call Langflow.
const resolved = { status: 'Resolved', name: 'Brand Model Shoes', brand: 'Brand', product_name: 'Model', item_type: 'Shoes', style_accent: null, evidence: '- Label shows Model', sources: 'https://example.com/product', candidate: null, missing_evidence: '', next_action: '', reason_unresolved: '' }
const needs = { ...resolved, status: 'Needs Evidence', name: null, product_name: null, candidate: 'Possible AB-12', missing_evidence: 'Interior label', next_action: 'Add a label photo.' }
const unresolved = { ...needs, status: 'Unresolved', missing_evidence: '', next_action: '', reason_unresolved: 'No further evidence.' }
const fake = () => ({ id: 'ui-test', langflow_session_id: 'identifier-m2-ui-test', execution_state: 'idle', images: [], attempts: [], result: null, decision: null, decisions: [], error: null })

async function harness(callback) {
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
  let session = fake()
  let next = needs
  let runCalls = 0
  const browserErrors = []
  page.on('pageerror', e => browserErrors.push(e.message))
  await page.route('**/api/**', async route => {
    const request = route.request(), url = new URL(request.url()), method = request.method()
    if (method === 'POST' && url.pathname === '/api/sessions') session = fake()
    if (url.pathname.endsWith('/identify')) {
      runCalls++
      session.execution_state = 'processing'; session.result = null; session.decision = null
      session.attempts.push({ number: runCalls, started_at: new Date().toISOString(), input: request.postDataJSON(), raw_final: '', parsed_result: null, runtime_seconds: null })
      const current = session, outcome = next
      setTimeout(() => {
        current.execution_state = outcome ? 'completed' : 'failed'
        current.result = outcome
        current.error = outcome ? null : 'Langflow returned HTTP 500.'
        current.attempts.at(-1).parsed_result = outcome
      }, 150)
    }
    if (url.pathname.endsWith('/decision')) {
      const body = request.postDataJSON()
      session.decision = { action: body.action, identity: body.identity || session.result }
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(session) })
  })
  try {
    await page.goto('http://127.0.0.1:5173')
    await page.getByRole('button', { name: 'Choose Photos' }).waitFor()
    await callback({ page, setNext: value => { next = value }, runs: () => runCalls })
    assert.deepEqual(browserErrors, [])
  } finally { await browser.close() }
}

async function manual(page) {
  await page.getByText('Add What I Know', { exact: false }).click()
  await page.getByRole('textbox', { name: 'Brand', exact: true }).fill('Brand')
  await page.getByRole('button', { name: 'Identify', exact: true }).click()
  await page.getByRole('status').waitFor()
  await page.getByRole('status').waitFor({ state: 'hidden' })
}

test('Needs Evidence, manual followup, exhausted evidence and general acceptance', async () => {
  await harness(async ({ page, setNext, runs }) => {
    await manual(page)
    await page.getByRole('button', { name: 'Add Another Photo' }).waitFor()
    assert.match(await page.locator('.candidate').textContent(), /Possible AB-12/)
    await page.getByRole('button', { name: 'Enter Information Manually' }).click()
    await page.getByRole('textbox', { name: 'Model / Style / SKU / UPC' }).fill('AB-12')
    await page.getByRole('button', { name: 'Identify with Added Evidence' }).click()
    await page.getByRole('status').waitFor()
    await page.getByRole('status').waitFor({ state: 'hidden' })
    setNext(unresolved)
    await page.getByRole('button', { name: "I Don't Have More Information" }).click()
    await page.getByRole('button', { name: 'Accept General Identity' }).waitFor()
    await page.getByText('Earlier evidence for this item', { exact: true }).click()
    assert.match(await page.locator('.earlier-evidence').textContent(), /AB-12/)
    await page.getByRole('button', { name: 'Accept General Identity' }).click()
    await page.getByText('General identity accepted', { exact: true }).waitFor()
    assert.equal(runs(), 3)
  })
})

test('Resolved correction makes no model call; rejection stays distinct', async () => {
  await harness(async ({ page, setNext, runs }) => {
    setNext(resolved)
    await manual(page)
    await page.getByRole('button', { name: 'Not This Item' }).click()
    await page.getByText('Rejected by you', { exact: true }).waitFor()
    assert.equal(await page.getByRole('button', { name: 'Looks Right' }).count(), 0)
    await page.getByRole('button', { name: 'Edit', exact: true }).click()
    await page.locator('.edit-form').getByRole('textbox', { name: 'Product Name', exact: true }).fill('Correct Model')
    await page.getByRole('button', { name: 'Save Correction' }).click()
    await page.getByText('Corrected by you', { exact: true }).waitFor()
    assert.match(await page.locator('.identity').textContent(), /Correct Model/)
    assert.match(await page.locator('.item-name').textContent(), /Brand Correct Model Shoes/)
    assert.equal(runs(), 1)
  })
})

test('Operational failure is not rendered as Unresolved', async () => {
  await harness(async ({ page, setNext }) => {
    setNext(null)
    await manual(page)
    await page.getByText('Execution failed', { exact: true }).waitFor()
    assert.equal(await page.getByRole('button', { name: 'Accept General Identity' }).count(), 0)
    await page.getByText('Debug / Technical Details', { exact: true }).click()
    assert.match(await page.locator('.debug').textContent(), /Langflow returned HTTP 500/)
  })
})
