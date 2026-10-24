const fs = require('node:fs');
const path = require('node:path');
const input = path.join(__dirname, 'PaperLab_Implementation_Plan.md');
const output = path.join(__dirname, 'PaperLab_Implementation_Plan.html');
const md = fs.readFileSync(input, 'utf8');
const esc = s => s.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
function inline(s) {
  let result = esc(s);
  result = result.replace(/\[([^\]]+)\]\((https:\/\/[^\s)]+)\)/g, '<a href="$2">$1</a>');
  result = result.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  result = result.replace(/`([^`]+)`/g, '<code>$1</code>');
  return result;
}
const lines = md.split(/\r?\n/);
const blocks = [], toc = [];
let i = 0, tableCount = 0, codeCount = 0;
while (i < lines.length) {
  const line = lines[i];
  if (!line.trim()) { i++; continue; }
  if (line.startsWith('```')) {
    const lang = line.slice(3).trim();
    let code = []; i++;
    while (i < lines.length && !lines[i].startsWith('```')) code.push(lines[i++]);
    if (i === lines.length) throw new Error('Unclosed code fence');
    i++; codeCount++;
    blocks.push(`<pre aria-label="${lang === 'json' ? 'Example change record' : 'Architecture or workflow outline'}"><code>${esc(code.join('\n'))}</code></pre>`);
    continue;
  }
  const heading = line.match(/^(#{1,3}) (.+)$/);
  if (heading) {
    const level = heading[1].length, title = heading[2];
    const id = title.toLowerCase().replace(/[^a-z0-9 ]/g, '').trim().replace(/ +/g, '-');
    if (level === 2) toc.push({id, title});
    blocks.push(`<h${level} id="${id}">${inline(title)}</h${level}>`); i++; continue;
  }
  if (line.startsWith('|')) {
    const rows = [];
    while (i < lines.length && lines[i].startsWith('|')) {
      const cells = lines[i++].slice(1).replace(/\|\s*$/, '').split('|').map(s => s.trim());
      if (!cells.every(c => /^:?-+:?$/.test(c))) rows.push(cells);
    }
    if (!rows.every(r => r.length === rows[0].length)) throw new Error('Unequal table columns');
    tableCount++;
    const th = rows[0].map(c => `<th scope="col">${inline(c)}</th>`).join('');
    const trs = rows.slice(1).map(row => '<tr>' + row.map(c => `<td>${inline(c)}</td>`).join('') + '</tr>').join('\n');
    blocks.push(`<div class="table-scroll"><table><thead><tr>${th}</tr></thead><tbody>${trs}</tbody></table></div>`);
    continue;
  }
  if (/^- /.test(line)) {
    const items=[];
    while(i < lines.length && /^- /.test(lines[i])) items.push(`<li>${inline(lines[i++].slice(2))}</li>`);
    blocks.push(`<ul>${items.join('\n')}</ul>`); continue;
  }
  if (/^\d+\. /.test(line)) {
    const items=[];
    while(i < lines.length && /^\d+\. /.test(lines[i])) items.push(`<li>${inline(lines[i++].replace(/^\d+\. /, ''))}</li>`);
    blocks.push(`<ol>${items.join('\n')}</ol>`); continue;
  }
  const para=[];
  while(i < lines.length && lines[i].trim() && !/^(#{1,3} |```|\||- |\d+\. )/.test(lines[i])) para.push(lines[i++]);
  blocks.push(`<p>${inline(para.join(' '))}</p>`);
}
const contents = toc.map(t => `<a href="#${t.id}">${esc(t.title)}</a>`).join('\n');
const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Implementation plan for PaperLab, including human feedback, agent roles, system architecture, roadmap and realistic scenarios.">
<title>PaperLab Implementation Plan</title>
<style>
:root{color-scheme:light;--ink:#17202b;--muted:#526170;--line:#d9d9d9;--blue:#173e62;--paper:#fff;--wash:#f3f6f9}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:30px}
body{margin:0;background:var(--wash);color:var(--ink);font:16px/1.65 'Segoe UI',Arial,sans-serif}
a{color:#155485;text-decoration-thickness:1px;text-underline-offset:3px;overflow-wrap:anywhere}
a:focus-visible,button:focus-visible{outline:3px solid #1e7abe;outline-offset:3px}
.layout{display:grid;grid-template-columns:270px minmax(0,960px);gap:42px;max-width:1320px;margin:auto;padding:36px 26px 72px}
nav{position:sticky;top:28px;align-self:start;font-size:13px;line-height:1.45;max-height:calc(100vh - 56px);overflow:auto;padding:12px 6px}
nav p{font-size:12px;font-weight:700;color:#000;letter-spacing:.08em;text-transform:uppercase;margin:0 0 18px}
nav a{display:block;color:#364554;text-decoration:none;margin:0 0 12px;padding:3px 0}
nav a:hover{color:#155485;text-decoration:underline}
main{background:var(--paper);padding:48px 54px 64px;border:1px solid #e3e8ec;min-width:0}
.tools{display:flex;justify-content:flex-end;gap:16px;align-items:center;font-size:13px;margin:0 0 32px;color:var(--muted)}
button{background:#fff;border:1px solid #9aa9b7;border-radius:4px;padding:8px 13px;color:#17202b;cursor:pointer;font:inherit}
h1,h2,h3{color:#000;line-height:1.23;font-weight:650;letter-spacing:-.02em;break-after:avoid}
h1{font-size:38px;margin:0 0 12px;max-width:640px}
h1+p{font-size:21px;line-height:1.45;color:#000;margin:0 0 10px}
h1+p+p{color:var(--muted);font-size:13px;margin-bottom:40px}
h2{font-size:25px;margin:52px 0 18px}
h3{font-size:19px;margin:30px 0 12px}
p{margin:0 0 17px}ul,ol{padding-left:24px;margin:12px 0 22px}li{padding-left:3px;margin:0 0 9px}
strong{font-weight:650}.table-scroll{overflow-x:auto;margin:22px 0 26px}
table{border-collapse:collapse;width:100%;font-size:13px;line-height:1.5;table-layout:fixed}
th,td{border:1px solid var(--line);padding:12px 13px;text-align:left;vertical-align:middle;overflow-wrap:break-word}
th{background:var(--blue);color:#fff;font-weight:650}tr:nth-child(even) td{background:#f2f6fa}
th:first-child,td:first-child{width:27%}thead{display:table-header-group}tr{break-inside:avoid}
pre{margin:20px 0 24px;padding:18px 20px;background:#f6f7f8;border:1px solid #d9d9d9;font:12px/1.65 Consolas,'Courier New',monospace;overflow-x:auto;white-space:pre;tab-size:2;break-inside:avoid}
code{font-family:Consolas,'Courier New',monospace;font-size:.9em}pre code{font-size:inherit}
footer{margin-top:40px;color:var(--muted);font-size:12px}
@media(max-width:1050px){.layout{grid-template-columns:210px minmax(0,1fr);gap:22px;padding:24px 16px}main{padding:36px 30px}h1{font-size:33px}}
@media(max-width:760px){.layout{display:block;padding:0}nav{position:static;max-height:none;padding:24px;background:#eaf0f5}nav a{display:inline-block;margin:0 16px 10px 0}main{border:0;padding:32px 22px}h1{font-size:31px}h2{font-size:23px}table{min-width:620px}pre{font-size:11px}}
@media print{@page{size:A4;margin:17mm 16mm 18mm}html{scroll-behavior:auto}body{background:#fff;color:#000;font:10pt/1.45 'Segoe UI',Arial,sans-serif}.layout{display:block;padding:0;margin:0;max-width:none}nav,.tools{display:none}main{padding:0;border:0;max-width:none}h1{font-size:26pt}h1+p{font-size:14pt}h1+p+p{font-size:9pt;margin-bottom:24pt}h2{font-size:17pt;margin:25pt 0 10pt}h3{font-size:12pt;margin:17pt 0 8pt}p{margin-bottom:9pt;orphans:3;widows:3}li{margin-bottom:5pt}.table-scroll{overflow:visible;margin:12pt 0 16pt}table{min-width:0;font-size:8.5pt;line-height:1.35}th,td{padding:7pt 8pt}th{background:#e8eef4!important;color:#000!important}tr:nth-child(even) td{background:#f6f7f8!important}pre{font-size:8pt;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere;padding:10pt}a{color:#000;text-decoration:underline}footer{font-size:8pt}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
</style>
</head>
<body>
<div class="layout">
<nav aria-label="Document contents"><p>Document contents</p>${contents}</nav>
<main id="main">
<div class="tools"><a href="PaperLab_Implementation_Plan.md" download>Editable Markdown</a><button type="button" onclick="window.print()">Print or save as PDF</button></div>
${blocks.join('\n')}
<footer>PaperLab implementation plan · 24 October 2026 · Version 1.0</footer>
</main>
</div>
</body>
</html>`;
fs.writeFileSync(output, html, 'utf8');
const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
if(new Set(ids).size !== ids.length) throw new Error('Duplicate heading IDs');
for(const ref of html.matchAll(/href="#([^"]+)"/g)) if(!ids.includes(ref[1])) throw new Error('Broken internal link');
if(toc.length !== 13) throw new Error('Unexpected section count');
if((md.match(/^### Scenario /gm)||[]).length !== 7) throw new Error('Missing scenario');
if(html.includes('undefined') || html.includes('[object Object]')) throw new Error('Invalid output');
console.log(JSON.stringify({output,sections:toc.length,tables:tableCount,codeBlocks:codeCount,scenarios:7,words:md.split(/\s+/).length,bytes:Buffer.byteLength(html)},null,2));
