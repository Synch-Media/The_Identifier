// Explicit live QA. Runs the actual configured workflow; never runs as an ordinary test.
import { chromium } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const root = path.resolve('..')
const evidence = path.join(root, 'data', 'milestone2', new Date().toISOString().replace(/[:.]/g, '-'))
await mkdir(evidence, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
const errors = []
page.on('pageerror', error => errors.push(error.message))
const report = { evidence, sessions: [], steps: [], browserErrors: errors }
const save = async () => writeFile(path.join(evidence, 'report.json'), JSON.stringify(report, null, 2))
async function snapshot(label) {
  const id = await page.evaluate(() => sessionStorage.getItem('identifierSession'))
  const response = await page.request.get(`http://127.0.0.1:5173/api/sessions/${id}`)
  const session = await response.json()
  await writeFile(path.join(evidence, label + '.json'), JSON.stringify(session, null, 2))
  await page.screenshot({ path: path.join(evidence, label + '.png'), fullPage: true })
  report.steps.push({ label, id, state: session.execution_state, status: session.result?.status, attempts: session.attempts.length, decision: session.decision?.action })
  await save()
  console.log(JSON.stringify(report.steps.at(-1)))
  return session
}
async function choose(relative) {
  await page.getByLabel('Choose product photos').setInputFiles(path.join(root, relative))
  await page.getByRole('button', { name: /Identify/, exact: false }).waitFor()
  await page.waitForFunction(() => [...document.querySelectorAll('button')].some(b => b.textContent.startsWith('Identify') && !b.disabled))
}
async function run(button = /^(Identify|Identify with Added Evidence)$/) {
  await page.getByRole('button', { name: button }).click()
  await page.getByRole('status').waitFor()
  await page.getByRole('status').waitFor({ state: 'hidden', timeout: 480_000 })
}
try {
  await page.goto('http://127.0.0.1:5173')
  await page.getByRole('button', { name: 'Choose Photos' }).waitFor()
  await page.waitForFunction(() => Boolean(sessionStorage.getItem('identifierSession')))
  await snapshot('00-empty')
  await choose('data/integration/20260925T170521157291Z-a-initial/originals/0.jpg')
  await snapshot('01-photo-uploaded')
  await run()
  let a = await snapshot('02-jeans-initial')
  report.sessions.push(a.id)
  if (a.execution_state !== 'completed') throw Error('Initial jeans run failed')
  if (a.result.status === 'Needs Evidence') {
    await choose('data/integration/20260925T170750219579Z-a-tag-followup/originals/0.jpg')
    await run()
    a = await snapshot('03-jeans-followup')
  }
  if (a.result.status !== 'Resolved') throw Error('Jeans follow-up did not resolve; review actual output')
  const originalCalls = a.attempts.length
  await page.getByRole('button', { name: 'Edit', exact: true }).click()
  await page.getByRole('textbox', { name: 'Product Name', exact: true }).fill('511 Slim')
  await page.getByRole('textbox', { name: 'Name', exact: true }).fill("Levi's 511 Slim Jeans")
  await page.getByRole('button', { name: 'Save Correction' }).click()
  await page.getByText('Corrected by you', { exact: true }).waitFor()
  a = await snapshot('04-manual-correction')
  if (a.attempts.length !== originalCalls || a.decision.identity.product_name !== '511 Slim') throw Error('Correction contract failed')
  await page.reload()
  await page.getByText('Corrected by you', { exact: true }).waitFor()
  await snapshot('05-refresh-retains-correction')
  await page.getByRole('button', { name: /Start New Item/ }).click()
  await page.waitForFunction(id => sessionStorage.getItem('identifierSession') !== id, a.id)
  const fresh = await snapshot('06-second-item-empty')
  if (fresh.images.length || fresh.attempts.length || fresh.result || fresh.langflow_session_id === a.langflow_session_id) throw Error('Session isolation failed')
  report.sessions.push(fresh.id)
  await choose('data/integration/20260925T170648308418Z-b-initial/originals/0.png')
  await run()
  let b = await snapshot('07-shoes-initial')
  if (b.execution_state !== 'completed') throw Error('Initial shoes run failed')
  if (b.result.status === 'Needs Evidence') {
    await page.getByRole('button', { name: 'Enter Information Manually' }).click()
    await page.getByRole('textbox', { name: 'Brand', exact: true }).fill('Goodfellow & Co.')
    await run()
    b = await snapshot('08-shoes-manual-evidence')
  }
  if (b.result.status === 'Needs Evidence') {
    await run("I Don't Have More Information")
    b = await snapshot('09-no-more-evidence')
  }
  if (b.result.status === 'Unresolved' && b.result.item_type && !b.result.product_name) {
    await page.getByRole('button', { name: 'Accept General Identity' }).click()
    await page.getByText('General identity accepted', { exact: true }).waitFor()
    await snapshot('10-general-identity')
  }
  await page.getByText('Debug / Technical Details', { exact: true }).click()
  await snapshot('11-debug')
  if (errors.length) throw Error('Browser console errors: ' + errors.join(', '))
  report.outcome = 'passed'
} catch (error) {
  report.outcome = 'failed'
  report.error = error.message
  await page.screenshot({ path: path.join(evidence, 'failure.png'), fullPage: true })
  console.error(error)
  process.exitCode = 1
} finally {
  await save()
  console.log('Evidence: ' + evidence)
  await browser.close()
}
