// Builds the League App canvas as one self-contained HTML file.
// Usage: node src/build.mjs draft|full
import fs from 'node:fs';
import path from 'node:path';
import { chip, icon } from './ui.mjs';

const ROOT = path.resolve(import.meta.dirname, '..');
const read = (p) => fs.readFileSync(path.join(ROOT, p), 'utf8');

const FONT_FILES = [
  ['Barlow', 400, 'barlow-latin-400-normal'],
  ['Barlow', 500, 'barlow-latin-500-normal'],
  ['Barlow', 600, 'barlow-latin-600-normal'],
  ['Barlow', 700, 'barlow-latin-700-normal'],
  ['Barlow Condensed', 600, 'barlow-condensed-latin-600-normal'],
  ['Barlow Condensed', 700, 'barlow-condensed-latin-700-normal'],
];
const fontFaces = FONT_FILES.map(([family, weight, file]) => {
  const b64 = fs.readFileSync(path.join(ROOT, 'fonts', `${file}.woff2`)).toString('base64');
  return `@font-face{font-family:"${family}";font-style:normal;font-weight:${weight};font-display:swap;src:url(data:font/woff2;base64,${b64}) format("woff2");}`;
}).join('\n');

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');

function board(b) {
  const tags = [];
  if (b.km) tags.push(chip('info', `Key moment ${b.km}`));
  if (b.theme === 'day') tags.push(chip('info', 'Day theme'));
  if (b.oq) tags.push(chip('pending', 'Open question'));
  if (b.lock) tags.push(chip('info', `${b.lock} push`));
  const frs = b.frs && b.frs.length ? ` — ${b.frs.join(', ')}` : '';
  const notes = [];
  if (b.oq) (Array.isArray(b.oq) ? b.oq : [b.oq]).forEach((q) => notes.push(`<p><b>Open question.</b> ${q}</p>`));
  if (b.note) notes.push(`<p>${b.note}</p>`);
  return `<figure class="cv-ab" data-ab="${b.id}">
<figcaption class="cv-ab__cap"><span class="cv-ab__name">${b.name}${frs}</span>${tags.length ? `<span class="cv-ab__tags">${tags.join('')}</span>` : ''}</figcaption>
<div class="cv-ab__frame">${b.html}</div>
${notes.length ? `<div class="cv-ab__note">${notes.join('')}</div>` : ''}
</figure>`;
}

function sep(kind) {
  if (kind === 'or') return '<div class="cv-sep cv-sep--or" aria-hidden="true">or</div>';
  if (kind === 'gap') return '<div class="cv-sep cv-sep--gap" aria-hidden="true">' + icon('more') + '</div>';
  return `<div class="cv-sep" aria-hidden="true">${icon('arrowR')}</div>`;
}

function row(r) {
  const parts = [];
  r.boards.forEach((b, i) => {
    if (i > 0) parts.push(sep(b.sep));
    parts.push(board(b));
  });
  return `<section class="cv-row" data-row="${r.id}" id="row-${r.id}">
<header class="cv-row__head"><p class="la-overline">${r.kicker}</p><h2>${r.name}</h2>${r.desc ? `<p class="body muted">${r.desc}</p>` : ''}</header>
<div class="cv-row__boards">${parts.join('\n')}</div>
</section>`;
}

const mode = process.argv[2] || 'draft';
const { canvas } = await import(mode === 'draft' ? './canvas-draft.mjs' : './canvas-full.mjs');
const c = canvas();

const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(c.title)}</title>
<style>
${read('src/ds/bundle.css')}
</style>
<style>
${read('src/ds/tokens.css')}
</style>
<style>
${fontFaces}
</style>
<style>
${read('src/proposed.css')}
</style>
<style>
${read('src/canvas.css')}
</style>
</head>
<body data-theme="night">
<div class="cv-toolbar" role="toolbar" aria-label="Zoom">
<button data-z="0.25">25%</button><button data-z="0.5" aria-pressed="true">50%</button><button data-z="0.75">75%</button><button data-z="1">100%</button>
</div>
<main class="cv" id="cv">
<header class="cv-head">
<p class="la-overline">${c.kicker}</p>
<h1>${c.title}</h1>
<p class="body muted" style="max-width:900px">${c.intro}</p>
<div class="cv-legend">${c.legend || ''}</div>
</header>
${(c.before || []).join('\n')}
${c.rows.map(row).join('\n')}
${(c.after || []).join('\n')}
</main>
<script>
(function () {
  var cv = document.getElementById('cv');
  var q = new URLSearchParams(location.search);
  var z = parseFloat(q.get('zoom') || '0.5');
  function setZoom(v) {
    cv.style.zoom = v;
    document.querySelectorAll('.cv-toolbar button').forEach(function (b) { b.setAttribute('aria-pressed', String(parseFloat(b.dataset.z) === v)); });
  }
  document.querySelectorAll('.cv-toolbar button').forEach(function (b) { b.addEventListener('click', function () { setZoom(parseFloat(b.dataset.z)); }); });
  setZoom(z);
  // Debug filters for screenshots: ?row=ID&ab=id1,id2&zoom=1&bare=1
  var rowId = q.get('row');
  if (rowId) {
    document.querySelectorAll('.cv-row').forEach(function (r) { if (r.dataset.row !== rowId) r.classList.add('cv-hidden'); });
    document.querySelectorAll('.cv-head, .cv-panel').forEach(function (h) { h.classList.add('cv-hidden'); });
  }
  var abs = q.get('ab');
  if (abs) {
    var keep = abs.split(',');
    document.querySelectorAll('.cv-ab').forEach(function (a) {
      if (keep.indexOf(a.dataset.ab) < 0) { a.classList.add('cv-hidden'); var s = a.previousElementSibling; if (s && s.classList.contains('cv-sep')) s.classList.add('cv-hidden'); }
    });
    document.querySelectorAll('.cv-row').forEach(function (r) { if (!r.querySelector('.cv-ab:not(.cv-hidden)')) r.classList.add('cv-hidden'); });
    document.querySelectorAll('.cv-head, .cv-panel').forEach(function (h) { h.classList.add('cv-hidden'); });
  }
  if (q.get('bare')) document.querySelector('.cv-toolbar').classList.add('cv-hidden');
})();
</script>
</body>
</html>
`;

const out = path.join(ROOT, c.file);
fs.writeFileSync(out, html);
const n = c.rows.reduce((a, r) => a + r.boards.length, 0);
console.log(`wrote ${c.file}: ${c.rows.length} rows, ${n} artboards, ${(html.length / 1024).toFixed(0)} KB`);
