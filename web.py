"""Sales Agent — FastAPI web dashboard."""

from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional

from config import PORT, COMPANY_NAME, TELEGRAM_BOT_TOKEN
from agent import run_skill, chat, clear_memory
from skills.prompts import SKILL_MAP
from database import init_db, get_leads, get_audit_log, get_metrics

app = FastAPI(title=f"{COMPANY_NAME} Sales Agent", version="1.0.0")
_tg_app = None

SKILL_COLORS = {
    "lead-qualify": "#f59e0b", "outreach-writer": "#6366f1", "follow-up-engine": "#8b5cf6",
    "call-prep": "#06b6d4", "objection-handler": "#ef4444", "deal-coach": "#10b981",
    "competitor-intel": "#f97316", "pipeline-analyzer": "#3b82f6",
}


@app.on_event("startup")
async def startup():
    global _tg_app
    init_db()
    from scheduler import start_scheduler
    start_scheduler()

    if TELEGRAM_BOT_TOKEN:
        try:
            from telegram_bot import build_application
            import os
            _tg_app = build_application()
            await _tg_app.initialize()
            domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
            if domain:
                await _tg_app.bot.set_webhook(f"https://{domain}/telegram/webhook")
            await _tg_app.start()
        except Exception as e:
            print(f"Telegram init error: {e}")


@app.on_event("shutdown")
async def shutdown():
    if _tg_app:
        await _tg_app.stop()
        await _tg_app.shutdown()


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    if not _tg_app:
        return {"ok": False}
    from telegram import Update
    data = await request.json()
    update = Update.de_json(data, _tg_app.bot)
    await _tg_app.process_update(update)
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def dashboard():
    try:
        from hubspot import get_pipeline_stats, get_new_contacts
        stats = get_pipeline_stats()
        contacts = get_new_contacts(limit=5)
        total_value = f"${stats['total_value']:,.0f}"
        total_deals = stats['total_deals']
        weighted = f"${stats['weighted_forecast']:,.0f}"
        contact_rows = "".join(
            f"<tr><td>{c['properties'].get('firstname','') or ''} {c['properties'].get('lastname','') or ''}</td>"
            f"<td class='muted'>{c['properties'].get('company','—')}</td>"
            f"<td class='muted'>{c['properties'].get('jobtitle','—')}</td>"
            f"<td class='muted'>{c['properties'].get('lifecyclestage','—')}</td></tr>"
            for c in contacts
        )
    except Exception:
        total_value, total_deals, weighted = "—", "—", "—"
        contact_rows = "<tr><td colspan='4' class='muted' style='text-align:center'>Connect HubSpot</td></tr>"

    metrics = get_metrics()
    total_runs = metrics.get("total", 0)
    leads_qualified = metrics.get("count_lead-qualify", 0)
    sequences_written = metrics.get("count_outreach-writer", 0)
    deals_coached = metrics.get("count_deal-coach", 0)

    skill_cards = ""
    for sk_id, sk in SKILL_MAP.items():
        color = SKILL_COLORS.get(sk_id, "#6366f1")
        skill_cards += f"""
        <div class="skill-card" onclick="selectSkill('{sk_id}')">
          <div class="skill-dot" style="background:{color}"></div>
          <div><div class="skill-name">{sk['name']}</div><div class="skill-desc">{sk['description']}</div></div>
        </div>"""

    today = datetime.now().strftime("%A, %B %d")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>{COMPANY_NAME} Sales Agent</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    :root{{--bg:#07070f;--s:#0e0e1c;--s2:#141428;--b:#1a1a30;--b2:#242445;--a:#6366f1;--a2:#818cf8;--green:#10b981;--red:#ef4444;--gold:#f59e0b;--text:#f0f0ff;--m:#55557a;--m2:#8080a8;--r:12px}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;font-size:14px}}
    header{{border-bottom:1px solid var(--b);padding:0 40px;height:64px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;background:rgba(7,7,15,.96);backdrop-filter:blur(16px);z-index:100}}
    .logo{{display:flex;align-items:center;gap:10px;font-weight:700;font-size:16px;text-decoration:none;color:var(--text)}}
    .logo-dot{{width:10px;height:10px;border-radius:50%;background:var(--a);box-shadow:0 0 12px var(--a)}}
    .nav a{{color:var(--m2);text-decoration:none;font-size:13px;margin-left:24px}}
    .nav a:hover{{color:var(--text)}}
    main{{max-width:1280px;margin:0 auto;padding:32px 40px 80px;display:grid;grid-template-columns:1fr 360px;gap:32px}}
    .left{{display:flex;flex-direction:column;gap:28px}}
    .right{{display:flex;flex-direction:column;gap:20px;position:sticky;top:80px;max-height:calc(100vh - 100px)}}
    .metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
    .m-card{{background:var(--s);border:1px solid var(--b);border-radius:var(--r);padding:18px 20px}}
    .m-val{{font-size:26px;font-weight:700}}
    .m-lbl{{font-size:11px;color:var(--m);text-transform:uppercase;letter-spacing:.5px;margin-top:4px}}
    .m-sub{{font-size:12px;color:var(--a2);margin-top:3px}}
    .section-label{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--m);margin-bottom:14px}}
    .skill-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
    .skill-card{{display:flex;align-items:flex-start;gap:12px;background:var(--s);border:1px solid var(--b);border-radius:var(--r);padding:14px 16px;cursor:pointer;transition:border-color .15s,background .15s}}
    .skill-card:hover,.skill-card.active{{border-color:var(--a);background:rgba(99,102,241,.06)}}
    .skill-dot{{width:8px;height:8px;border-radius:50%;margin-top:5px;flex-shrink:0}}
    .skill-name{{font-weight:600;font-size:13px}}
    .skill-desc{{font-size:12px;color:var(--m2);margin-top:2px;line-height:1.4}}
    .runner{{background:var(--s);border:1px solid var(--b);border-radius:var(--r);overflow:hidden}}
    .runner-hdr{{padding:14px 20px;border-bottom:1px solid var(--b);background:var(--s2);font-weight:600;font-size:14px;display:flex;align-items:center;gap:8px}}
    .runner-body{{padding:20px;display:flex;flex-direction:column;gap:12px}}
    .runner-body label{{font-size:12px;color:var(--m2);font-weight:500;display:block;margin-bottom:4px}}
    .runner-body select,.runner-body textarea,.runner-body input{{width:100%;background:var(--bg);border:1px solid var(--b2);border-radius:8px;color:var(--text);padding:10px 12px;font-size:13px;font-family:inherit;outline:none;transition:border-color .15s}}
    .runner-body select:focus,.runner-body textarea:focus,.runner-body input:focus{{border-color:var(--a)}}
    .runner-body textarea{{resize:vertical;min-height:90px}}
    .run-btn{{background:var(--a);color:#fff;border:none;border-radius:8px;padding:11px;font-size:13px;font-weight:700;cursor:pointer;width:100%;transition:opacity .15s}}
    .run-btn:hover{{opacity:.85}}
    .run-btn:disabled{{opacity:.4;cursor:not-allowed}}
    .result{{background:var(--bg);border:1px solid var(--b);border-radius:8px;padding:16px;font-size:13px;line-height:1.7;white-space:pre-wrap;display:none;max-height:420px;overflow-y:auto}}
    .result.show{{display:block}}
    .chat-panel{{background:var(--s);border:1px solid var(--b);border-radius:var(--r);display:flex;flex-direction:column;flex:1;min-height:0}}
    .chat-hdr{{padding:14px 18px;border-bottom:1px solid var(--b);background:var(--s2);border-radius:var(--r) var(--r) 0 0;display:flex;align-items:center;gap:10px}}
    .online{{width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 6px var(--green);flex-shrink:0}}
    .chat-title{{font-weight:600;font-size:13px}}
    .chat-sub{{font-size:11px;color:var(--m2)}}
    .chat-msgs{{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;min-height:200px;max-height:350px}}
    .msg{{padding:10px 13px;border-radius:10px;font-size:13px;line-height:1.6;white-space:pre-wrap;max-width:92%}}
    .msg.user{{background:rgba(99,102,241,.18);border:1px solid rgba(99,102,241,.3);align-self:flex-end;border-radius:10px 10px 2px 10px}}
    .msg.bot{{background:var(--s2);border:1px solid var(--b2);align-self:flex-start;border-radius:10px 10px 10px 2px}}
    .msg.sys{{color:var(--m);font-size:12px;text-align:center;align-self:center;background:none;border:none}}
    .chat-input-row{{padding:10px;border-top:1px solid var(--b);display:flex;gap:8px}}
    .chat-in{{flex:1;background:var(--bg);border:1px solid var(--b2);border-radius:8px;color:var(--text);padding:9px 12px;font-size:13px;font-family:inherit;outline:none;resize:none;transition:border-color .15s}}
    .chat-in:focus{{border-color:var(--a)}}
    .send-btn{{background:var(--a);color:#fff;border:none;border-radius:8px;padding:9px 14px;cursor:pointer;transition:opacity .15s;flex-shrink:0}}
    .send-btn:disabled{{opacity:.4}}
    .table-wrap{{background:var(--s);border:1px solid var(--b);border-radius:var(--r);overflow:hidden}}
    table{{width:100%;border-collapse:collapse}}
    th{{text-align:left;padding:10px 16px;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;color:var(--m);background:var(--s2);border-bottom:1px solid var(--b)}}
    td{{padding:10px 16px;border-bottom:1px solid var(--b);font-size:13px}}
    tr:last-child td{{border-bottom:none}}
    .muted{{color:var(--m2)}}
    .spinner{{display:inline-block;width:13px;height:13px;border:2px solid rgba(129,140,248,.3);border-top-color:var(--a2);border-radius:50%;animation:spin .7s linear infinite;margin-right:6px;vertical-align:middle}}
    @keyframes spin{{to{{transform:rotate(360deg)}}}}
    @media(max-width:960px){{main{{grid-template-columns:1fr}}.right{{position:static}}.metrics{{grid-template-columns:repeat(2,1fr)}}.skill-grid{{grid-template-columns:1fr}}}}
  </style>
</head>
<body>
<header>
  <a class="logo" href="/"><span class="logo-dot"></span>{COMPANY_NAME} Sales Agent</a>
  <nav class="nav">
    <a href="#skills">Skills</a><a href="#pipeline">Pipeline</a><a href="/linkedin">LinkedIn</a><a href="/audit">Audit</a><a href="/docs">API</a>
  </nav>
</header>
<main>
  <div class="left">
    <div>
      <div style="margin-bottom:8px;color:var(--m2);font-size:13px">{today}</div>
      <h1 style="font-size:28px;font-weight:700;margin-bottom:4px">Sales Intelligence Engine</h1>
      <p style="color:var(--m2)">8 AI skills. Auto-qualify leads. Coach every deal. Close faster.</p>
    </div>

    <div class="metrics">
      <div class="m-card"><div class="m-val">{total_deals}</div><div class="m-lbl">Open Deals</div><div class="m-sub">{weighted} weighted</div></div>
      <div class="m-card"><div class="m-val">{total_value}</div><div class="m-lbl">Pipeline Value</div></div>
      <div class="m-card"><div class="m-val">{leads_qualified}</div><div class="m-lbl">Leads Qualified</div></div>
      <div class="m-card"><div class="m-val">{sequences_written}</div><div class="m-lbl">Sequences Written</div></div>
    </div>

    <div id="skills">
      <div class="section-label">8 Sales Skills</div>
      <div class="skill-grid">{skill_cards}</div>
    </div>

    <div class="runner" id="runner">
      <div class="runner-hdr">⚡ Run a Skill</div>
      <div class="runner-body">
        <div>
          <label>Skill</label>
          <select id="skillSel">{"".join(f'<option value="{sk_id}">{SKILL_MAP[sk_id]["name"]}</option>' for sk_id in SKILL_MAP)}</select>
        </div>
        <div>
          <label>Context (company, product, ICP)</label>
          <input type="text" id="ctx" placeholder="e.g. B2B SaaS, targeting ops teams, seed stage"/>
        </div>
        <div>
          <label>Input</label>
          <textarea id="inp" placeholder="Paste lead data, deal info, objection, competitor name..."></textarea>
        </div>
        <button class="run-btn" id="runBtn" onclick="runSkill()">Run</button>
        <div class="result" id="res"></div>
      </div>
    </div>

    <div id="pipeline">
      <div class="section-label">Pipeline by Stage</div>
      <div style="background:var(--s);border:1px solid var(--b);border-radius:var(--r);padding:20px;margin-bottom:16px">
        <canvas id="pipelineChart" height="160"></canvas>
      </div>
      <div class="section-label">Recent HubSpot Contacts</div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Name</th><th>Company</th><th>Title</th><th>Stage</th></tr></thead>
          <tbody>{contact_rows}</tbody>
        </table>
      </div>
    </div>
  </div>

  <div class="right">
    <div class="chat-panel">
      <div class="chat-hdr">
        <span class="online"></span>
        <div><div class="chat-title">Sales AI Chat</div><div class="chat-sub">Ask anything about leads, deals, outreach</div></div>
      </div>
      <div class="chat-msgs" id="msgs">
        <div class="msg sys">Ask about a lead, deal, objection, or anything sales-related.</div>
      </div>
      <div class="chat-input-row">
        <textarea class="chat-in" id="chatIn" rows="1" placeholder="Message..." onkeydown="handleKey(event)"></textarea>
        <button class="send-btn" id="sendBtn" onclick="send()">➤</button>
      </div>
    </div>
  </div>
</main>

<script>
const sid = 'web-' + Math.random().toString(36).slice(2,8);

// Pipeline chart
(async function(){{
  try {{
    const d = await fetch('/pipeline/data').then(r=>r.json());
    if(!d.labels||!d.labels.length) return;
    const ctx = document.getElementById('pipelineChart').getContext('2d');
    new Chart(ctx, {{
      type: 'bar',
      data: {{
        labels: d.labels,
        datasets: [
          {{ label: 'Deal Value ($)', data: d.values, backgroundColor: 'rgba(99,102,241,0.7)', borderColor: '#6366f1', borderWidth: 1, borderRadius: 6 }},
          {{ label: 'Weighted ($)', data: d.weighted, backgroundColor: 'rgba(16,185,129,0.5)', borderColor: '#10b981', borderWidth: 1, borderRadius: 6 }}
        ]
      }},
      options: {{
        responsive: true, maintainAspectRatio: true,
        plugins: {{ legend: {{ labels: {{ color: '#8080a8', font: {{ size: 12 }} }} }} }},
        scales: {{
          x: {{ ticks: {{ color: '#8080a8', font: {{ size: 11 }} }}, grid: {{ color: 'rgba(255,255,255,0.05)' }} }},
          y: {{ ticks: {{ color: '#8080a8', font: {{ size: 11 }}, callback: v => '$'+v.toLocaleString() }}, grid: {{ color: 'rgba(255,255,255,0.05)' }} }}
        }}
      }}
    }});
  }} catch(e) {{ console.log('Chart error', e); }}
}})();

function selectSkill(id){{
  document.getElementById('skillSel').value=id;
  document.querySelectorAll('.skill-card').forEach(c=>c.classList.remove('active'));
  event.currentTarget.classList.add('active');
  document.getElementById('runner').scrollIntoView({{behavior:'smooth',block:'center'}});
}}

async function runSkill(){{
  const skill=document.getElementById('skillSel').value;
  const input=document.getElementById('inp').value.trim();
  const context=document.getElementById('ctx').value.trim();
  if(!input){{alert('Enter your input.');return;}}
  const btn=document.getElementById('runBtn'),res=document.getElementById('res');
  btn.disabled=true;btn.innerHTML='<span class="spinner"></span>Analyzing...';
  res.className='result show';res.textContent='Thinking...';
  try{{
    const r=await fetch('/skill/sync',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{skill,input,context,session_id:sid}})}});
    const d=await r.json();res.textContent=d.result||d.detail||'No result.';
  }}catch(e){{res.textContent='Error: '+e.message;}}
  btn.disabled=false;btn.innerHTML='Run';
}}

function handleKey(e){{if(e.key==='Enter'&&!e.shiftKey){{e.preventDefault();send();}}}}

function addMsg(role,text){{
  const d=document.createElement('div');d.className='msg '+role;d.textContent=text;
  const m=document.getElementById('msgs');m.appendChild(d);m.scrollTop=m.scrollHeight;return d;
}}

async function send(){{
  const inp=document.getElementById('chatIn');
  const msg=inp.value.trim();if(!msg)return;
  inp.value='';addMsg('user',msg);
  const btn=document.getElementById('sendBtn');btn.disabled=true;
  const ph=addMsg('bot','...');
  try{{
    const r=await fetch('/chat',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{message:msg,session_id:sid}})}});
    const d=await r.json();ph.textContent=d.reply||d.detail||'No response.';
  }}catch(e){{ph.textContent='Error: '+e.message;}}
  btn.disabled=false;
}}
</script>
</body>
</html>"""


class ChatReq(BaseModel):
    message: str
    session_id: Optional[str] = "web"

class SkillReq(BaseModel):
    skill: str
    input: str
    context: Optional[str] = ""
    session_id: Optional[str] = "web"


@app.post("/chat")
def chat_endpoint(req: ChatReq):
    try:
        return {"reply": chat(req.message, req.session_id or "web")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/skill/sync")
def skill_sync(req: SkillReq):
    if req.skill not in SKILL_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown skill '{req.skill}'")
    try:
        return {"skill": req.skill, "result": run_skill(req.skill, req.input, req.context or "", req.session_id or "web")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/qualify/trigger")
def trigger_qualify():
    import threading
    from scheduler import auto_qualify_new_leads
    threading.Thread(target=auto_qualify_new_leads, daemon=True).start()
    return {"status": "running"}


class LinkedInReq(BaseModel):
    name: str
    title: str
    company: str
    location: Optional[str] = "Dubai"
    industry: Optional[str] = ""
    notes: Optional[str] = ""
    product_context: Optional[str] = ""


@app.post("/linkedin/generate")
def linkedin_generate(req: LinkedInReq):
    try:
        prompt = f"""Write a hyper-personalized LinkedIn outreach sequence for this prospect:

Name: {req.name}
Title: {req.title}
Company: {req.company}
Location: {req.location}
Industry: {req.industry}
Additional notes: {req.notes}

Product/Service being sold: {req.product_context or "Dubai life setup service — fixed price AED 15,000, covers residency, banking, utilities, healthcare, schools in 3 weeks"}

Write:
1. CONNECTION REQUEST NOTE (max 300 chars) — personal, not salesy
2. OPENER MESSAGE (after they accept) — reference something specific about them, lead with value, one clear CTA
3. FOLLOW-UP 1 (day 3) — add specific value relevant to their industry/role
4. FOLLOW-UP 2 (day 6) — social proof angle
5. FOLLOW-UP 3 (day 10) — direct ROI challenge
6. BREAKUP MESSAGE (day 13) — short, walk away, triggers response

Make each message feel hand-written, not templated. Use their specific industry context."""

        result = run_skill("outreach-writer", prompt, req.product_context or "", "linkedin-gen")
        return {"name": req.name, "messages": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/linkedin", response_class=HTMLResponse)
def linkedin_page():
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>LinkedIn Outreach Generator</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    :root{{--bg:#07070f;--s:#0e0e1c;--s2:#141428;--b:#1a1a30;--b2:#242445;--a:#6366f1;--a2:#818cf8;--green:#10b981;--text:#f0f0ff;--m:#55557a;--m2:#8080a8;--r:12px}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;font-size:14px;padding:32px 40px}}
    h1{{font-size:24px;font-weight:700;margin-bottom:6px}}
    .sub{{color:var(--m2);margin-bottom:28px;font-size:14px}}
    .grid{{display:grid;grid-template-columns:400px 1fr;gap:24px;max-width:1100px}}
    .card{{background:var(--s);border:1px solid var(--b);border-radius:var(--r);padding:20px;display:flex;flex-direction:column;gap:12px}}
    label{{font-size:12px;color:var(--m2);font-weight:500;display:block;margin-bottom:3px}}
    input,textarea{{width:100%;background:var(--bg);border:1px solid var(--b2);border-radius:8px;color:var(--text);padding:9px 12px;font-size:13px;font-family:inherit;outline:none}}
    input:focus,textarea:focus{{border-color:var(--a)}}
    textarea{{resize:vertical;min-height:70px}}
    .btn{{background:var(--a);color:#fff;border:none;border-radius:8px;padding:11px;font-size:13px;font-weight:700;cursor:pointer;width:100%}}
    .btn:disabled{{opacity:.4}}
    .btn:hover{{opacity:.85}}
    .result-card{{background:var(--s);border:1px solid var(--b);border-radius:var(--r);padding:20px}}
    .msg-block{{background:var(--bg);border:1px solid var(--b2);border-radius:8px;padding:14px;margin-bottom:12px;position:relative}}
    .msg-label{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--a2);margin-bottom:8px}}
    .msg-text{{font-size:13px;line-height:1.7;white-space:pre-wrap;color:var(--text)}}
    .copy-btn{{position:absolute;top:10px;right:10px;background:var(--b2);color:var(--m2);border:none;border-radius:6px;padding:4px 10px;font-size:11px;cursor:pointer}}
    .copy-btn:hover{{color:var(--text)}}
    .spinner{{display:inline-block;width:13px;height:13px;border:2px solid rgba(129,140,248,.3);border-top-color:var(--a2);border-radius:50%;animation:spin .7s linear infinite;margin-right:6px;vertical-align:middle}}
    @keyframes spin{{to{{transform:rotate(360deg)}}}}
    .back{{color:var(--m2);text-decoration:none;font-size:13px;display:inline-block;margin-bottom:20px}}
    .back:hover{{color:var(--text)}}
    .section-title{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--m);margin-bottom:14px}}
    @media(max-width:800px){{.grid{{grid-template-columns:1fr}}body{{padding:20px}}}}
  </style>
</head>
<body>
  <a class="back" href="/">← Back to Sales Agent</a>
  <h1>LinkedIn Outreach Generator</h1>
  <p class="sub">Paste any LinkedIn profile → get a personalized 6-message sequence instantly.</p>

  <div class="grid">
    <div class="card">
      <div class="section-title">Profile Info</div>
      <div><label>Full Name</label><input id="name" placeholder="James Mitchell"/></div>
      <div><label>Job Title</label><input id="title" placeholder="Founder & CEO"/></div>
      <div><label>Company</label><input id="company" placeholder="Fintech Startup"/></div>
      <div><label>Location</label><input id="location" placeholder="Dubai, UAE" value="Dubai, UAE"/></div>
      <div><label>Industry</label><input id="industry" placeholder="Fintech, SaaS, Real Estate..."/></div>
      <div><label>Notes (recent post, mutual connection, anything specific)</label><textarea id="notes" placeholder="Just moved from London, posted about Dubai's startup ecosystem last week..."></textarea></div>
      <div><label>Your Product/Service (optional — defaults to Dubai setup service)</label><textarea id="product" placeholder="Leave blank to use Dubai life setup service AED 15,000"></textarea></div>
      <button class="btn" id="genBtn" onclick="generate()">Generate Messages</button>
    </div>

    <div class="result-card">
      <div class="section-title">Generated Sequence</div>
      <div id="output"><p style="color:var(--m2);font-size:13px">Fill in the profile on the left and click Generate.</p></div>
    </div>
  </div>

<script>
async function generate(){{
  const name=document.getElementById('name').value.trim();
  const title=document.getElementById('title').value.trim();
  const company=document.getElementById('company').value.trim();
  if(!name||!title||!company){{alert('Name, title and company are required.');return;}}
  const btn=document.getElementById('genBtn');
  const out=document.getElementById('output');
  btn.disabled=true;
  btn.innerHTML='<span class="spinner"></span>Generating...';
  out.innerHTML='<p style="color:var(--m2);font-size:13px">Writing personalized messages — this takes 15–20 seconds...</p>';
  try{{
    const r=await fetch('/linkedin/generate',{{
      method:'POST',
      headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{
        name,title,company,
        location:document.getElementById('location').value,
        industry:document.getElementById('industry').value,
        notes:document.getElementById('notes').value,
        product_context:document.getElementById('product').value
      }})
    }});
    if(!r.ok){{
      const err=await r.json().catch(()=>({{detail:'Server error '+r.status}}));
      out.innerHTML=`<p style="color:#ef4444;font-size:13px">Error ${{r.status}}: ${{err.detail||r.statusText}}</p>`;
      return;
    }}
    const d=await r.json();
    const text=d.messages||d.detail||'No response received';
    const safe=text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    out.innerHTML=`<div class="msg-block"><div class="msg-label">SEQUENCE FOR ${{name.toUpperCase()}}</div><button class="copy-btn" onclick="copyBlock(this)">Copy All</button><div class="msg-text">${{safe}}</div></div>`;
  }}catch(e){{
    out.innerHTML=`<p style="color:#ef4444;font-size:13px">Error: ${{e.message}}</p>`;
  }}finally{{
    btn.disabled=false;
    btn.innerHTML='Generate Messages';
  }}
}}

function copyMsg(btn){{
  const text=btn.nextElementSibling.textContent;
  navigator.clipboard.writeText(text).then(()=>{{btn.textContent='Copied!';setTimeout(()=>btn.textContent='Copy',1500);}}).catch(()=>alert(btn.nextElementSibling.textContent));
}}
function copyBlock(btn){{
  const text=btn.nextElementSibling.textContent;
  navigator.clipboard.writeText(text).then(()=>{{btn.textContent='Copied!';setTimeout(()=>btn.textContent='Copy All',1500);}}).catch(()=>alert(text));
}}
</script>
</body>
</html>"""


@app.get("/audit")
def audit():
    return get_audit_log(limit=100)


@app.get("/leads")
def leads(tier: str = None):
    return get_leads(limit=100, tier=tier)


@app.get("/metrics")
def metrics_endpoint():
    return get_metrics()


@app.get("/pipeline/data")
def pipeline_data():
    try:
        from hubspot import get_pipeline_stats
        stats = get_pipeline_stats()
        stages = stats.get("stages", {})
        return {
            "labels": list(stages.keys()),
            "values": [round(s["value"]) for s in stages.values()],
            "weighted": [round(s["weighted"]) for s in stages.values()],
            "counts": [s["count"] for s in stages.values()],
            "total_deals": stats["total_deals"],
            "total_value": stats["total_value"],
            "weighted_forecast": stats["weighted_forecast"],
        }
    except Exception as e:
        return {"labels": [], "values": [], "weighted": [], "counts": [], "error": str(e)}


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web:app", host="0.0.0.0", port=PORT, reload=False)
