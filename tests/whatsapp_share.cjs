const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const html = fs.readFileSync(path.join(__dirname, '../api/template.html'), 'utf8');
const start = html.indexOf('    whatsappBtn.addEventListener("click"');
const end = html.indexOf('    // ===== Scroll Indicator', start);
assert.ok(start >= 0 && end > start);

const titleStart = html.indexOf('          const title = JSON.parse(');
const titleEnd = html.indexOf('          generatedPosters.push', titleStart);
assert.ok(titleStart >= 0 && titleEnd > titleStart);
const readTitle = html.slice(titleStart, titleEnd) + '\nresult = title;';
for (const title of ['שבת שלום וחג שמח', 'ברכה עם 100% ו-%20', 'ברכה "אישית"\nבשתי שורות']) {
  const context = {
    resp: { headers: { get: () => JSON.stringify(title) } },
    mainTitleOverride: '', getDefaultTitleForEvent: () => 'שבת שלום',
  };
  vm.runInNewContext(readTitle, context);
  assert.equal(context.result, title);
}

async function check(title, nativeShare, type = 'image/png') {
  let handler, shared, opened;
  const context = {
    whatsappBtn: { addEventListener: (_, fn) => { handler = fn; } },
    generatedPosters: [{ blob: { type }, title }],
    omerModeEnabled: false,
    // Current form state must not replace the already generated poster title.
    selectedEventName: { textContent: 'שבת/חג הקרוב' },
    mainTitleInput: { value: 'כותרת ששונתה לאחר היצירה' },
    getFileExtension: blob => blob.type === 'image/gif' ? 'gif' : 'png',
    File: class { constructor(parts, name, options) { this.name = name; this.type = options.type; } },
    navigator: { canShare: () => nativeShare, share: async data => { shared = data; } },
    window: { open: url => { opened = url; } },
    encodeURIComponent,
  };
  vm.runInNewContext(html.slice(start, end), context);
  await handler();
  const expected = `${title} 🕯️\n\nנוצר באמצעות: https://shabat-posts.vercel.app/`;
  if (nativeShare) {
    assert.equal(shared.title, title);
    assert.equal(shared.text, expected);
    assert.equal(shared.files[0].type, type);
    assert.equal(opened, undefined);
  } else {
    assert.equal(new URL(opened).searchParams.get('text'), expected + '\n\n(הורד/י את התמונה מהאתר)');
  }
}

(async () => {
  for (const title of ['שבת שלום', 'שבת שלום וחג שמח', 'חג שמח', 'גמר חתימה טובה', 'ברכה אישית']) {
    await check(title, true);
    await check(title, false);
  }
  await check('שבת שלום וחג שמח', true, 'image/gif');
  console.log('WhatsApp sharing: 11 cases passed');
})().catch(error => { console.error(error); process.exit(1); });
