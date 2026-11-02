"""Friendly local Flask dashboard for PartySync."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from flask import Flask, jsonify, request

from partysync.cli import fake_backend
from partysync.core.mixing import ChannelMode
from partysync.engine import Engine

PAGE = """<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PartySync Web</title><style>
:root{--bg:#08111f;--card:#102039;--line:#294866;--text:#eef7ff;--muted:#9eb5ca;--mint:#55e6a5;--blue:#7aacff}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 90% 0,#194a70,transparent 42%),var(--bg);color:var(--text);font:15px system-ui}main{max-width:1000px;margin:auto;padding:24px}header{display:flex;justify-content:space-between;gap:20px;align-items:center;margin-bottom:18px}.brand{display:flex;gap:12px;align-items:center}.icon{font-size:26px;background:linear-gradient(135deg,var(--mint),var(--blue));padding:9px 14px;border-radius:14px;color:#07111f}.tag,.eyebrow{font-size:11px;font-weight:800;letter-spacing:.1em;color:var(--mint)}h1{margin:1px 0;font-size:27px}.sub,.hint{color:var(--muted)}.tag{border:1px solid var(--line);border-radius:999px;padding:8px;color:#f9c15d}.bar,.card{background:rgba(16,32,57,.94);border:1px solid var(--line);border-radius:18px}.bar{padding:15px;display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap}.buttons{display:flex;gap:8px;flex-wrap:wrap}button{border:0;border-radius:10px;background:#25415f;color:var(--text);font-weight:700;padding:10px 13px;cursor:pointer}.primary{background:linear-gradient(135deg,#42ce91,#35aee3);color:#07111f}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}.card{padding:18px}.head{display:flex;justify-content:space-between;align-items:start}.head h2{margin:3px 0;font-size:20px}.meter{height:10px;border-radius:8px;background:#07111f;margin:18px 0 7px;overflow:hidden}.meter i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--mint),#d8ff7d);transition:width .18s}.b .meter i{background:linear-gradient(90deg,var(--blue),#c5a6ff)}.stats{display:flex;justify-content:space-between;color:var(--muted);font-size:12px}.field{margin-top:18px}.field label{display:flex;justify-content:space-between;font-weight:700;margin-bottom:7px}.field label span{color:var(--mint)}.b .field label span{color:var(--blue)}input{width:100%;accent-color:var(--mint)}.b input{accent-color:var(--blue)}.nudges,.modes{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-top:8px}.nudges button,.modes button{font-size:12px;padding:8px 3px}.bottom{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}@media(max-width:700px){main{padding:14px}header{display:block}.tag{display:inline-block;margin-top:12px}.grid,.bottom{grid-template-columns:1fr}}
</style><main><header><div class="brand"><div class="icon">♫</div><div><div class="eyebrow">LOCAL AUDIO ROUTER</div><h1>PartySync Web</h1><div class="sub">Tune two speakers until they sound like one.</div></div></div><div class="tag" id="state">SIMULATED · STOPPED</div></header>
<section class="bar"><div><b>Source: VB-Audio Virtual Cable</b><div class="hint">Simulation is active until real Windows device selection is enabled.</div></div><div class="buttons"><button class="primary" onclick="start()">Start simulation</button><button onclick="calibrate()">Auto-calibrate</button><button onclick="stop()">Stop</button></div></section>
<section class="grid"><article class="card" id="A"></article><article class="card b" id="B"></article></section><section class="bottom"><article class="card"><div class="eyebrow">SYNC TESTER</div><h2>Listen for a single click</h2><p class="hint">With real speakers connected, use delay nudges until double clicks become one.</p></article><article class="card"><div class="eyebrow">CALIBRATION</div><h2 id="calhead">Ready to calibrate</h2><p class="hint" id="caltext">Start the simulation, then auto-calibrate to see virtual delay compensation.</p></article></section></main>
<script>
let s={a:{},b:{}};function api(url,data){return fetch(url,{method:data?'POST':'GET',headers:{'Content-Type':'application/json'},body:data?JSON.stringify(data):null}).then(r=>r.json())}
function card(k,title,name){let x=s[k]||{},d=Number(x.delay_ms||0),p=Math.min(100,(x.peak||0)*100),g=Math.round((x.gain||1)*100);return '<div class="head"><div><div class="eyebrow">SPEAKER '+title+'</div><h2>'+name+'</h2><div class="hint">'+(title==='A'?'Compensation target':'Reference speaker')+'</div></div><b class="hint">'+(x.primed?'READY':'BUFFERING')+'</b></div><div class="meter"><i style="width:'+p+'%"></i></div><div class="stats"><span>Peak '+(x.peak||0).toFixed(2)+'</span><span>Fill '+(x.fill_ms||0).toFixed(0)+' ms</span><span>Slips '+(x.slips||0)+'</span></div><div class="field"><label>Delay <span>'+d.toFixed(1)+' ms</span></label><input type="range" min="0" max="1000" step=".5" value="'+d+'" oninput="send(\\''+k+'\\',\\'delay_ms\\',this.value)"><div class="nudges"><button onclick="nudge(\\''+k+'\\',-10)">-10 ms</button><button onclick="nudge(\\''+k+'\\',-1)">-1 ms</button><button onclick="nudge(\\''+k+'\\',1)">+1 ms</button><button onclick="nudge(\\''+k+'\\',10)">+10 ms</button></div></div><div class="field"><label>Volume <span>'+g+'%</span></label><input type="range" min="0" max="150" value="'+g+'" oninput="send(\\''+k+'\\',\\'gain\\',this.value/100)"></div><div class="modes"><button onclick="send(\\''+k+'\\',\\'mode\\',\\'stereo\\')">Stereo</button><button onclick="send(\\''+k+'\\',\\'mode\\',\\'mono\\')">Mono</button><button onclick="send(\\''+k+'\\',\\'mode\\',\\'left\\')">Left</button><button onclick="send(\\''+k+'\\',\\'mode\\',\\'right\\')">Right</button></div><button style="width:100%;margin-top:12px" onclick="send(\\''+k+'\\',\\'muted\\','+(!x.muted)+')">'+(x.muted?'Unmute speaker':'Mute speaker')+'</button>'}
function render(data){s=data;document.getElementById('A').innerHTML=card('a','A','JBL Flip 7 Stereo');document.getElementById('B').innerHTML=card('b','B','JBL Charge 4 Stereo');document.getElementById('state').textContent='SIMULATED · '+(data.running?'PLAYING':'STOPPED')}function refresh(){api('/api/status').then(render)}function start(){api('/api/start',{}).then(render)}function stop(){api('/api/stop',{}).then(render)}function send(k,f,v){api('/api/control',{channel:k.toUpperCase(),[f]:f==='muted'?Boolean(v):v}).then(render)}function nudge(k,n){send(k,'delay_ms',Math.max(0,Number(s[k].delay_ms||0)+n))}function calibrate(){api('/api/calibrate',{}).then(r=>{document.getElementById('calhead').textContent=r.ok?'Calibration applied':'Calibration failed';document.getElementById('caltext').textContent=r.ok?'Speaker B is '+r.delta_ms.toFixed(1)+' ms slower. Speaker A is delayed by '+r.delay_a_ms.toFixed(1)+' ms.':r.reason;refresh()})}setInterval(refresh,250);refresh();
</script>"""


def create_app() -> Flask:
    """Create the local web remote application."""
    app = Flask(__name__)
    backend = fake_backend()
    engine = Engine(backend)

    @app.get("/")
    def index():
        return PAGE

    @app.get("/api/status")
    def status():
        state = engine.stats().__dict__ | {"simulated": True}
        for key in ("a", "b"):
            state[key] |= {"gain": 1.0, "mode": "stereo", "muted": False}
        return jsonify(state)

    @app.post("/api/start")
    def start():
        if not engine.running:
            engine.start(backend.list_sources()[0], *backend.list_outputs()[:2])
            backend.world.run(0.1)
        return status()

    @app.post("/api/stop")
    def stop():
        engine.stop()
        return status()

    @app.post("/api/control")
    def control():
        data = request.get_json(force=True)
        channel = data.get("channel", "A")
        if "delay_ms" in data:
            engine.set_delay_ms(channel, float(data["delay_ms"]))
        if "gain" in data:
            engine.set_gain(channel, float(data["gain"]))
        if "muted" in data:
            engine.set_muted(channel, bool(data["muted"]))
        if "mode" in data:
            engine.set_mode(channel, ChannelMode(data["mode"]))
        return status()

    @app.post("/api/calibrate")
    def calibrate():
        return jsonify(engine.calibrate_simulated().__dict__)

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000)
