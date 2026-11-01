"""PartySync Flask mobile dashboard; run with python app_flask.py."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))
from flask import Flask, jsonify, request
from partysync.cli import fake_backend
from partysync.engine import Engine
from partysync.core.mixing import ChannelMode

def create_app() -> Flask:
    """Create the local web remote application."""
    app=Flask(__name__); backend=fake_backend(); engine=Engine(backend)
    @app.get("/")
    def index():
        return """<meta name=viewport content='width=device-width'><body style='background:#111;color:#eee;font:16px system-ui;padding:2rem'><h1>PartySync Web</h1><p>Local Bluetooth sync remote</p><button onclick=\"fetch('/api/start',{method:'POST'}).then(status)\">Start simulation</button><pre id=s></pre><script>const status=()=>fetch('/api/status').then(x=>x.json()).then(x=>s.textContent=JSON.stringify(x,null,2));setInterval(status,250);status()</script></body>"""
    @app.get("/api/devices")
    def devices(): return jsonify({"sources":[d.__dict__ for d in backend.list_sources()],"outputs":[d.__dict__ for d in backend.list_outputs()],"mics":[d.__dict__ for d in backend.list_mics()]})
    @app.get("/api/status")
    def status(): return jsonify(engine.stats().__dict__ | {"simulated":True})
    @app.post("/api/start")
    def start():
        if not engine.running: engine.start(backend.list_sources()[0],*backend.list_outputs()[:2]); backend.world.run(.1)
        return status()
    @app.post("/api/stop")
    def stop(): engine.stop(); return status()
    @app.post("/api/control")
    def control():
        data=request.get_json(force=True); ch=data.get("channel","A")
        if "delay_ms" in data: engine.set_delay_ms(ch,float(data["delay_ms"]))
        if "gain" in data: engine.set_gain(ch,float(data["gain"]))
        if "muted" in data: engine.set_muted(ch,bool(data["muted"]))
        if "mode" in data: engine.set_mode(ch,ChannelMode(data["mode"]))
        return status()
    return app
if __name__=="__main__": create_app().run(host="0.0.0.0",port=5000)
