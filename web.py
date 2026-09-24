"""web.py — a free-deploy web doorway for Socket-Store.

WHY THIS FILE EXISTS
--------------------
Socket-Store's real interface is a raw TCP "phone line", which free web hosts
(like Render) only expose over HTTP. web.py keeps Socket-Store itself running
for real — it launches the actual asyncio TCP server from server.py on
127.0.0.1:8888 inside this process — and then adds a small HTTP front door:
a browser console + a tiny REST API. Every web request opens a REAL socket to
the real database, so what runs on the internet genuinely IS Socket-Store.

Run it locally:
    pip install -r requirements.txt
    python web.py            -> http://localhost:5000

Deploy for free: Render reads render.yaml and runs `waitress-serve web:app`.
"""

import asyncio
import os
import socket
import threading
import time

from flask import Flask, jsonify, request

import server as socket_store

# ---------------------------------------------------------------------------
# Start the REAL TCP database on a background thread (one event loop, many
# concurrent clients — exactly the same architecture as running server.py).
# ---------------------------------------------------------------------------

DB_HOST = "127.0.0.1"
DB_PORT = int(os.environ.get("DB_PORT", "8888"))
DATABASE = socket_store.DatabaseServer(host=DB_HOST, port=DB_PORT)


def _run_database() -> None:
    asyncio.run(DATABASE.start())


threading.Thread(target=_run_database, name="socket-store", daemon=True).start()


def _wait_for_database(timeout: float = 10.0) -> None:
    """Block until the TCP server is accepting connections."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((DB_HOST, DB_PORT), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("Socket-Store TCP server did not start in time")


_wait_for_database()

# ---------------------------------------------------------------------------
# The web layer
# ---------------------------------------------------------------------------

app = Flask(__name__)


def _send_command(command: str) -> str:
    """Send one command to the real TCP database and read the single-line reply."""
    with socket.create_connection((DB_HOST, DB_PORT), timeout=5.0) as sock:
        sock.sendall(command.encode("utf-8") + b"\n")
        reply = bytearray()
        while not reply.endswith(b"\n"):
            chunk = sock.recv(1)
            if not chunk:
                break
            reply += chunk
        return reply.decode("utf-8").strip()


@app.get("/")
def home():
    return CONSOLE_PAGE


@app.get("/api/health")
def health():
    return jsonify(ok=True, engine="Socket-Store", listening=f"{DB_HOST}:{DB_PORT}")


@app.post("/api/command")
def run_command():
    data = request.get_json(silent=True) or {}
    command = str(data.get("command", "")).strip()
    if not command:
        return jsonify(error="Empty command"), 400
    try:
        reply = _send_command(command)
    except (ConnectionError, OSError) as exc:
        return jsonify(error=f"Database unreachable: {exc}"), 503
    return jsonify(command=command, response=reply)


CONSOLE_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Socket-Store — Redis Clone in the Browser</title>
<style>
  *{box-sizing:border-box}
  body{margin:0;background:#0d1117;color:#e6edf3;font-family:ui-monospace,Consolas,"Cascadia Code",monospace;display:flex;flex-direction:column;height:100vh}
  header{padding:16px 20px;border-bottom:1px solid #30363d;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
  .dot{width:12px;height:12px;border-radius:50%;background:#3fb950;box-shadow:0 0 10px #3fb950}
  h1{font-size:16px;margin:0}
  .hint{font-size:12px;color:#8b949e;margin-left:auto}
  main{flex:1;padding:20px;overflow-y:auto}
  .line{white-space:pre-wrap;padding-bottom:6px}
  .cmd{color:#79c0ff}.out{color:#7ee787}.err{color:#ff7b72}.meta{color:#8b949e}
  .row{display:flex;align-items:center;border-top:1px solid #21262d}
  .prompt{color:#3fb950;padding:12px 14px}
  input{flex:1;background:#161b22;border:0;color:#e6edf3;font:inherit;padding:12px 0;outline:none}
  button{background:#238636;color:#fff;border:0;cursor:pointer;padding:12px 20px;font:inherit}
  button:hover{background:#2ea043}
  footer{padding:10px 20px;border-top:1px solid #21262d;color:#8b949e;font-size:12px}
</style>
</head>
<body>
<header>
  <span class="dot"></span>
  <h1>Socket-Store <span class="meta">- a Redis clone running your real asyncio TCP engine</span></h1>
  <span class="hint" id="conn">checking engine...</span>
</header>
<main id="term"></main>
<div class="row">
  <span class="prompt">&gt;</span>
  <input id="inp" autofocus autocomplete="off" placeholder="SET name Alice"/>
  <button id="send">Run</button>
</div>
<footer>Commands: SET / GET / DELETE / EXISTS / KEYS / EXPIRE / TTL / INCR / DECR / FLUSH / PING (type "help")</footer>
<script>
  var term=document.getElementById('term'), inp=document.getElementById('inp'), conn=document.getElementById('conn');
  function line(cls,txt){var d=document.createElement('div');d.className='line '+cls;d.textContent=txt;term.appendChild(d);term.scrollTop=term.scrollHeight;return d}
  async function run(cmd){
    if(!cmd.trim())return;
    line('cmd','$ '+cmd);
    try{
      var r=await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command:cmd})});
      var j=await r.json();
      if(r.ok)line('out',String(j.response));else line('err','ERROR: '+(j.error||r.status));
    }catch(e){line('err','ERROR: '+e.message)}
  }
  async function health(){
    try{var r=await fetch('/api/health');var j=await r.json();conn.textContent='engine online - '+j.listening;conn.style.color='#3fb950'}
    catch(e){conn.textContent='engine offline';conn.style.color='#ff7b72'}
  }
  async function submit(){var v=inp.value;inp.value='';await run(v)}
  document.getElementById('send').onclick=submit;
  inp.addEventListener('keydown',function(e){if(e.key==='Enter')submit()});
  line('meta','Connected. Try: SET name Alice  ->  GET name  ->  KEYS');
  health();
</script>
</body>
</html>"""


if __name__ == "__main__":
    from waitress import serve

    port = int(os.environ.get("PORT", "5000"))
    print(f"Socket-Store web console running on http://localhost:{port}")
    serve(app, host="0.0.0.0", port=port)