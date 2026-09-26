// Explicit additional live test: actual WebP, drag/drop, removal, no-more-evidence.
import { chromium } from '@playwright/test'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import path from 'node:path'
const root = path.resolve('..')
const output = path.join(root, 'data/milestone2/exhausted')
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
const report = { steps: [] }
async function capture(label) {
  const id = await page.evaluate(() => sessionStorage.getItem('identifierSession'))
  const state = await (await page.request.get(`http://127.0.0.1:5173/api/sessions/${id}`)).json()
  await writeFile(path.join(output, label + '.json'), JSON.stringify(state, null, 2))
  await page.screenshot({ path: path.join(output, label + '.png'), fullPage: true })
  report.session = id
  report.steps.push({ label, status: state.result?.status, execution: state.execution_state, attempts: state.attempts.length })
  console.log(JSON.stringify(report.steps.at(-1)))
  return state
}
async function run(name) {
  await page.getByRole('button', { name, exact: true }).click()
  await page.getByRole('status').waitFor()
  await page.getByRole('status').waitFor({ state: 'hidden', timeout: 480000 })
}
try {
  await page.goto('http://127.0.0.1:5173')
  await page.waitForFunction(() => sessionStorage.getItem('identifierSession'))
  const bytes = await readFile(path.join(root, 'data/milestone2/shoes.webp'))
  const transfer = await page.evaluateHandle(bytes => {
    const dt = new DataTransfer()
    dt.items.add(new File([new Uint8Array(bytes)], 'shoes.webp', { type: 'image/webp' }))
    return dt
  }, [...bytes])
  await page.locator('.dropzone').dispatchEvent('drop', { dataTransfer: transfer })
  await page.getByRole('button', { name: 'Remove shoes.webp' }).click()
  await page.waitForFunction(() => document.querySelectorAll('figure').length === 0)
  await page.getByLabel('Choose product photos').setInputFiles(path.join(root, 'data/milestone2/shoes.webp'))
  await page.waitForFunction(() => [...document.querySelectorAll('button')].some(b => b.textContent.startsWith('Identify') && !b.disabled))
  await run('Identify')
  let result = await capture('01-webp-initial')
  if (result.result?.status !== 'Needs Evidence') throw Error('Expected an evidence request for this fixture')
  await run("I Don't Have More Information")
  result = await capture('02-exhausted')
  if (result.execution_state !== 'completed') throw Error('No-more-evidence execution failed')
  if (result.result.status === 'Unresolved' && result.result.item_type && !result.result.product_name) {
    await page.getByRole('button', { name: 'Accept General Identity' }).click()
    await page.getByText('General identity accepted', { exact: true }).waitFor()
    await capture('03-general-accepted')
  }
  report.outcome = 'passed'
} catch (error) { report.outcome = 'failed'; report.error = error.message; console.error(error); process.exitCode = 1 }
finally {
  await writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2))
  await browser.close()
}
