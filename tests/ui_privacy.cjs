const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('api/template.html', 'utf8');
function source(name, next) {
  return html.slice(html.indexOf(`    function ${name}(`), html.indexOf(next, html.indexOf(`    function ${name}(`)));
}
const selectors = [];
const cityNodes = new Map(['חיפה', 'ירושלים'].map(name => [name, {dataset:{name}, classList:{add:()=>{}}}]));
const context = {
  URLSearchParams, window: {location: {origin:'http://localhost', pathname:'/', search:''}},
  omerModeEnabled:false, currentNusach:'sefard', orderedSelectedCities:['חיפה','ירושלים'],
  messageInput:{value:'ברכה 100% <img src=x onerror=alert(1)>'}, neshamaInput:{value:'לזכר 100% שלום'},
  document: {getElementById:()=>({checked:false}), querySelectorAll:()=>[], querySelector:s=>{selectors.push(s); return null;}},
  localStorage:{getItem:()=>null}, isOmerPeriodAvailable:true, DEFAULT_CITIES:[],
  setMode:()=>{}, setNusach:()=>{}, renderChips:()=>{}, updateCityLimit:()=>{},
  urlParamsNotice:{classList:{add:()=>{}}}, loadedFromUrl:false,
  escapeAttrForSelector:s=>s, findCityOption:name=>cityNodes.get(name),
};
vm.createContext(context);
vm.runInContext(source('generateShareableUrl', '    // Copy link button handler'), context);
vm.runInContext(source('loadFromUrlParams', '    // Clear URL params'), context);
const defaultLink = new URL(context.generateShareableUrl());
assert.equal(defaultLink.searchParams.has('message'), false, 'personal text must be opt-in');
assert.equal(defaultLink.searchParams.has('neshama'), false);
assert.equal(defaultLink.searchParams.get('cities'), 'חיפה,ירושלים', 'share must preserve selected order');

// New Omer links must carry an explicit nusach so recipient browser state cannot override it.
const savedNusachBySharedNusach = {
  sefard: 'ashkenaz',
  ashkenaz: 'edot_hamizrach',
  edot_hamizrach: 'sefard',
};
context.omerModeEnabled = true;
for (const [sharedNusach, savedNusach] of Object.entries(savedNusachBySharedNusach)) {
  context.currentNusach = sharedNusach;
  const sharedLink = new URL(context.generateShareableUrl());
  assert.equal(sharedLink.searchParams.get('nusach'), sharedNusach);
  context.currentNusach = savedNusach;
  context.localStorage.getItem = key => key === 'nusach' ? savedNusach : null;
  context.setNusach = nusach => { context.currentNusach = nusach; };
  context.window.location.search = sharedLink.search;
  context.loadFromUrlParams();
  assert.equal(context.currentNusach, sharedNusach, `${sharedNusach} link must override saved ${savedNusach}`);
}
context.currentNusach = 'sefard';
context.localStorage.getItem = key => key === 'nusach' ? 'ashkenaz' : null;
context.window.location.search = '?mode=omer';
context.loadFromUrlParams();
assert.equal(context.currentNusach, 'ashkenaz', 'legacy link without nusach must retain saved-preference fallback');
context.omerModeEnabled = false;
context.localStorage.getItem = () => null;
context.orderedSelectedCities = ['חיפה', 'ירושלים'];
context.document.getElementById=()=>({checked:true});
const included = new URL(context.generateShareableUrl());
assert.equal(included.searchParams.get('message'), context.messageInput.value);
context.window.location.search=included.search;
const message=context.messageInput.value, neshama=context.neshamaInput.value;
context.messageInput.value=''; context.neshamaInput.value='';
context.loadFromUrlParams();
assert.equal(context.messageInput.value,message);
assert.equal(context.neshamaInput.value,neshama);
assert.equal(Array.from(context.orderedSelectedCities).join(','),'חיפה,ירושלים');
// Legacy links contain one URL encoding, including literal percent escapes and markup.
context.window.location.search='?cities=%3Cimg%20src%3Dx%3E%25&message=100%25%20%D7%A9%D7%9C%D7%95%D7%9D%20%2520&neshama=%3Cscript%3E';
context.loadFromUrlParams();
assert.equal(context.messageInput.value,'100% שלום %20');
assert.equal(context.neshamaInput.value,'<script>');
assert(!html.includes('decodeURIComponent('));
assert(!html.includes('/_vercel/'));
assert(!html.includes('fonts.googleapis.com'));
assert(!html.includes('video/mp4'));
assert.match(html, /id="shareIncludeTexts"/);
assert.match(html, /id="cropHorizontal"/);
console.log('Sharing defaults, ordered city round trip, legacy percent/Hebrew/inert markup, local assets: passed');

// Closing an already-closed picker must not steal reorder focus.
let isOpen = false, focusCalls = 0;
context.cityPicker = {classList:{contains:()=>isOpen, remove:()=>{isOpen=false;}}};
context.addCityBtn = {focus:()=>{focusCalls++;}};
vm.runInContext(source('closeCityPicker', '    // Update city picker'), context);
context.closeCityPicker();
assert.equal(focusCalls, 0);
isOpen=true;
context.closeCityPicker();
assert.equal(focusCalls, 1);
console.log('Picker close preserves ordering focus: passed');
