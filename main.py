from flask import Flask, request, render_template_string
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
    'Accept-Language': 'en-US,en;q=0.9'
}

stop_events = {}
threads = {}

# --- COOKIE PARSER ---
def parse_cookie_string(cookie_str):
    cookie_dict = {}
    for pair in cookie_str.strip().split(';'):
        if '=' in pair:
            k, v = pair.strip().split('=', 1)
            cookie_dict[k] = v
    return cookie_dict

# --- MESSAGE SENDER ---
def send_messages(cookies_list, uid_tid, haters_name, time_interval, messages, task_key):
    stop_event = stop_events[task_key]
    while not stop_event.is_set():
        for msg in messages:
            if stop_event.is_set():
                break
            for cookie in cookies_list:
                api_url = f'https://graph.facebook.com/v15.0/t_{uid_tid}/'
                message = f"{haters_name} {msg}"
                try:
                    response = requests.post(api_url, data={'message': message}, headers=headers, cookies=cookie)
                    if response.status_code == 200:
                        print(f"[SUCCESS] {message} -> {uid_tid}")
                    else:
                        print(f"[FAILED] {message} -> {uid_tid} | Status: {response.status_code}")
                except Exception as e:
                    print(f"[ERROR] {e}")
                time.sleep(time_interval)

# --- RUN BOT ---
@app.route('/', methods=['GET', 'POST'])
def start_bot():
    if request.method == 'POST':
        cookie_option = request.form.get('cookieOption')
        cookies_list = []

        if cookie_option == 'single':
            raw_cookie = request.form.get('singleCookie')
            cookies_list = [parse_cookie_string(raw_cookie)]
        elif cookie_option == 'multi_raw':
            raw_cookies_file = request.files['rawCookiesFile']
            raw_cookies_list = raw_cookies_file.read().decode().splitlines()
            cookies_list = [parse_cookie_string(c) for c in raw_cookies_list]
        else:
            cookie_file = request.files['cookieFile']
            try:
                cookies_list = json.load(cookie_file)
            except:
                return "Invalid JSON file!"

        uid_tid = request.form.get('uidTid')
        haters_name = request.form.get('hatersName')
        time_interval = int(request.form.get('timeInterval'))
        np_file = request.files['npFile']
        messages = np_file.read().decode().splitlines()

        # Random stop key
        task_key = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

        stop_events[task_key] = Event()
        thread = Thread(target=send_messages, args=(cookies_list, uid_tid, haters_name, time_interval, messages, task_key))
        threads[task_key] = thread
        thread.start()

        return f"Task started! Your stop key is: <b>{task_key}</b>"

    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Facebook Messenger Bot</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body { background:#222; color:white; }
.container { max-width:600px; background:#333; margin-top:30px; padding:20px; border-radius:10px; }
.form-control { background:transparent; color:white; border:1px solid #fff; }
.btn-submit { width:100%; margin-top:10px; }
</style>
</head>
<body>
<div class="container text-center">
<h2>Facebook Messenger Bot</h2>
<form method="post" enctype="multipart/form-data">
<div class="mb-3">
<label>Cookie Option</label>
<select class="form-control" id="cookieOption" name="cookieOption" onchange="toggleCookieInput()" required>
<option value="single">Single Raw Cookie</option>
<option value="multi_raw">Multiple Raw Cookies File</option>
<option value="json_file">Cookie JSON File</option>
</select>
</div>

<div class="mb-3" id="singleCookieInput">
<label>Enter Single Raw Cookie</label>
<textarea class="form-control" name="singleCookie" rows="3"></textarea>
</div>

<div class="mb-3" id="multiRawInput" style="display:none;">
<label>Upload Raw Cookies File (one per line)</label>
<input type="file" class="form-control" name="rawCookiesFile">
</div>

<div class="mb-3" id="cookieFileInput" style="display:none;">
<label>Upload Cookie JSON File</label>
<input type="file" class="form-control" name="cookieFile">
</div>

<div class="mb-3">
<label>Haters Name</label>
<input type="text" class="form-control" name="hatersName" required>
</div>
<div class="mb-3">
<label>UID/TID (Inbox/Group ID)</label>
<input type="text" class="form-control" name="uidTid" required>
</div>
<div class="mb-3">
<label>Time Interval (seconds)</label>
<input type="number" class="form-control" name="timeInterval" required>
</div>
<div class="mb-3">
<label>Messages File (.txt)</label>
<input type="file" class="form-control" name="npFile" required>
</div>
<button type="submit" class="btn btn-primary btn-submit">Run</button>
</form>

<hr>
<h5>Stop Task</h5>
<form method="post" action="/stop">
<div class="mb-3">
<label>Enter Stop Key</label>
<input type="text" class="form-control" name="taskKey" required>
</div>
<button type="submit" class="btn btn-danger btn-submit">Stop</button>
</form>
</div>

<script>
function toggleCookieInput() {
var opt = document.getElementById('cookieOption').value;
document.getElementById('singleCookieInput').style.display = (opt=='single')?'block':'none';
document.getElementById('multiRawInput').style.display = (opt=='multi_raw')?'block':'none';
document.getElementById('cookieFileInput').style.display = (opt=='json_file')?'block':'none';
}
</script>
</body>
</html>
''')

# --- STOP ROUTE ---
@app.route('/stop', methods=['POST'])
def stop_task():
    task_key = request.form.get('taskKey')
    if task_key in stop_events:
        stop_events[task_key].set()
        return f"Task stopped successfully! ({task_key})"
    return "Invalid stop key!"

# --- KEEP ALIVE FOR RENDER / BOT HOSTING ---
@app.route('/ping')
def ping():
    return "Bot is alive!"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
