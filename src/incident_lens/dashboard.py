from __future__ import annotations

# Embedded asset is intentionally compact; browser code is not Python-formatted.
# ruff: noqa: E501, RUF001

DASHBOARD_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Incident Lens</title><style>
:root{color-scheme:dark;--bg:#091019;--card:#111c29;--line:#26384c;--text:#e8f0f7;--muted:#91a5b8;--cyan:#35d0ba;--red:#ff6577;--amber:#ffbd59}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 80% 0,#16344b 0,var(--bg) 32%);font:14px system-ui;color:var(--text)}
header{padding:22px 5vw;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}h1{margin:0;font-size:24px}header span,.muted{color:var(--muted)}main{padding:24px 5vw 60px;max-width:1500px;margin:auto}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:16px}.card{background:linear-gradient(145deg,#132131,var(--card));border:1px solid var(--line);border-radius:12px;padding:18px}.wide{grid-column:span 8}.narrow{grid-column:span 4}.full{grid-column:1/-1}h2{font-size:13px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);margin:0 0 16px}.service-map{display:flex;align-items:center;justify-content:center;gap:10px;min-height:110px}.node{padding:13px 15px;border:1px solid #377c83;border-radius:8px;background:#102b33}.arrow{color:var(--cyan);font-size:22px}.slo{display:grid;grid-template-columns:2fr repeat(3,1fr);gap:8px;padding:10px 0;border-top:1px solid var(--line)}.good{color:var(--cyan)}.bad{color:var(--red)}.hypothesis{padding:14px;border-left:3px solid var(--amber);background:#171f2a;margin:10px 0}.rank{font-size:22px;color:var(--amber);float:left;margin-right:14px}.rule{color:var(--muted);margin:5px 0}.timeline{border-left:2px solid #31506b;margin-left:8px}.event{padding:0 0 18px 18px;position:relative}.event:before{content:'';width:9px;height:9px;border-radius:50%;background:var(--cyan);position:absolute;left:-5px;top:5px}.links a{color:var(--cyan);margin-left:18px;text-decoration:none}.empty{padding:24px;color:var(--muted);text-align:center}@media(max-width:900px){.wide,.narrow{grid-column:1/-1}.service-map{flex-wrap:wrap}.slo{grid-template-columns:1fr 1fr}}
</style></head><body><header><div><h1>Incident Lens</h1><span>Transparent multi-signal diagnosis</span></div><div class="links"><a href="http://localhost:3000/d/incident-lens">Grafana</a><a href="http://localhost:3000/explore">Traces &amp; logs</a><a href="/docs">API</a></div></header>
<main><div class="grid"><section class="card full"><h2>Live service map</h2><div class="service-map"><div class="node">Checkout API</div><div class="arrow">→</div><div class="node">Order service</div><div class="arrow">→</div><div class="node">Payment service</div><div class="arrow">→</div><div class="node">PostgreSQL + Redis</div></div></section>
<section class="card wide"><h2>Current incident &amp; ranked hypotheses</h2><div id="incident" class="empty">Waiting for an SLO violation…</div></section>
<section class="card narrow"><h2>Incident timeline</h2><div id="timeline" class="empty">No incident events</div></section>
<section class="card full"><h2>Service-level objectives</h2><div id="slos"></div></section></div></main>
<script>
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=n=>(100*n).toFixed(3)+'%';const tm=n=>new Date(n*1000).toLocaleTimeString();
async function refresh(){
 const [sloRes,incidentRes]=await Promise.all([fetch('/api/slos'),fetch('/api/analyze',{method:'POST'})]);
 const slos=await sloRes.json(), result=await incidentRes.json();
 document.querySelector('#slos').innerHTML=slos.map(s=>`<div class="slo"><strong>${esc(s.definition.name)}</strong><span class="${s.compliance>=s.definition.target?'good':'bad'}">${pct(s.compliance)}</span><span>Budget ${pct(s.budget_remaining)}</span><span>${s.short_burn_rate.toFixed(1)}× burn</span></div>`).join('');
 if(!result.incident)return;const i=result.incident;
 document.querySelector('#incident').innerHTML=`<h3>${esc(i.title)}</h3>`+i.hypotheses.map(h=>`<div class="hypothesis"><span class="rank">#${h.rank}</span><strong>${esc(h.title)} · ${esc(h.service)}</strong><div>${h.score.toFixed(1)} evidence points</div>${h.contributions.map(c=>`<div class="rule">+${c.points.toFixed(1)} ${esc(c.explanation)} · ${c.evidence_ids.length} cited signal(s)</div>`).join('')}</div>`).join('');
 document.querySelector('#timeline').innerHTML=`<div class="timeline">${i.timeline.map(e=>`<div class="event"><span class="muted">${tm(e.timestamp)}</span><br>${esc(e.event)}</div>`).join('')}</div>`;
}refresh();setInterval(refresh,3000);
</script></body></html>"""
