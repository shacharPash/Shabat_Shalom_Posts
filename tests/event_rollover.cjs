const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '../api/template.html'), 'utf8');
const start = html.indexOf('    btn.addEventListener("click", async () => {');
const end = html.indexOf('    // Get file extension', start);
assert.ok(start >= 0 && end > start);

async function generate(explicit, refreshFails = false) {
  let click, payload, refreshes = 0;
  const classList = { add() {}, remove() {} };
  const context = {
    messageInput: { value: '' }, neshamaInput: { value: '' },
    fileInput: { files: [] }, omerModeEnabled: false,
    selectedDates: ['2026-09-18'], dateSelectionExplicit: explicit,
    statusEl: {}, btn: { classList, addEventListener: (_, fn) => { click = fn; } },
    previewEl: { classList }, generatedPosters: [], orderedSelectedCities: [],
    selectedDateFormat: 'both', selectedAspectRatio: 'square',
    mainTitleInput: { value: '' }, overrideMainTitle: { value: '' },
    overrideSubtitle: { value: '' }, getCustomCities: () => [],
    console: { error() {} },
    loadUpcomingEvents: async () => {
      refreshes++;
      context.selectedDates = refreshFails ? [''] : ['2026-09-20'];
    },
    fetch: async (_, options) => {
      payload = JSON.parse(options.body);
      // Stop after observing the real request, before gallery DOM rendering.
      return { ok: false, text: async () => 'test transport stopped' };
    },
  };
  vm.createContext(context);
  vm.runInContext(html.slice(start, end), context);
  await click();
  assert.ok(payload, context.statusEl.textContent);
  assert.equal(context.btn.disabled, false);
  return { payload, refreshes };
}

(async () => {
  const automatic = await generate(false);
  assert.equal(automatic.refreshes, 1);
  assert.equal(automatic.payload.startDate, '2026-09-20');
  const explicit = await generate(true);
  assert.equal(explicit.refreshes, 0);
  assert.equal(explicit.payload.startDate, '2026-09-18');
  const unavailable = await generate(false, true);
  assert.equal(unavailable.payload.startDate, undefined);
  console.log('Automatic rollover, explicit date, and server-default fallback passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
