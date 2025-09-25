from flask import Flask, request, render_template_string
import requests
from threading import Thread, Event
import time
import random
import string
import json

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
    'referer': 'www.google.com'
}

stop_events = {}
threads = {}

def send_messages(cookies_list, thread_id, mn, time_interval, messages, task_id):
    stop_event = stop_events[task_id]
    while not stop_event.is_set():
        for message1 in messages:
            if stop_event.is_set():
                break
            for cookie in cookies_list:
                api_url = f'https://graph.facebook.com/v15.0/t_{thread_id}/'
                message = f"{mn} {message1}"
                response = requests.post(api_url, data={'message': message}, headers=headers, cookies=cookie)
                if response.status_code == 200:
                    print(f"Message Sent Successfully From cookie {cookie}: {message}")
                else:
                    print(f"Message Sent Failed From cookie {cookie}: {message}")
                time.sleep(time_interval)

@app.route('/', methods=['GET', 'POST'])
def send_message():
    if request.method == 'POST':
        cookie_option = request.form.get('cookieOption')

        # Single cookie input
        if cookie_option == 'single':
            cookie_str = request.form.get('singleCookie')
            try:
                cookies_list = [json.loads(cookie_str)]
            except json.JSONDecodeError:
                return "Invalid JSON for single cookie."
        # Multiple cookies from uploaded JSON file
        else:
            cookie_file = request.files['cookieFile']
            try:
                cookies_list = json.load(cookie_file)
                if not isinstance(cookies_list, list):
                    return "Cookie file must contain a JSON array of cookie objects."
            except json.JSONDecodeError:
                return "Invalid JSON file."

        thread_id = request.form.get('threadId')
        mn = request.form.get('kidx')
        time_interval = int(request.form.get('time'))

        txt_file = request.files['txtFile']
        messages = txt_file.read().decode().splitlines()

        task_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

        stop_events[task_id] = Event()
        thread = Thread(target=send_messages, args=(cookies_list, thread_id, mn, time_interval, messages, task_id))
        threads[task_id] = thread
        thread.start()

        return f'Task started with ID: {task_id}'

    # HTML form with cookie input fields
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Facebook Cookie Messenger</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body { background-color:#222; color:white; }
.container { max-width:400px; padding:20px; border-radius:10px; margin-top:30px; background:#333; }
.form-control { background:transparent; color:white; border:1px solid #fff; }
</style>
</head>
<body>
<div class="container text-center">
<form method="post" enctype="multipart/form-data">
<div class="mb-3">
<label for="cookieOption">Select Cookie Option</label>
<select class="form-control" id="cookieOption" name="cookieOption" onchange="toggleCookieInput()" required>
<option value="single">Single Cookie (JSON)</option>
<option value="multiple">Cookie File (JSON Array)</option>
</select>
</div>
<div class="mb-3" id="singleCookieInput">
<label for="singleCookie">Enter Single Cookie JSON</label>
<textarea class="form-control" id="singleCookie" name="singleCookie" rows="3"></textarea>
</div>
<div class="mb-3" id="cookieFileInput" style="display:none;">
<label for="cookieFile">Choose Cookie JSON File</label>
<input type="file" class="form-control" id="cookieFile" name="cookieFile">
</div>
<div class="mb-3">
<label for="threadId">Enter Inbox/Convo UID</label>
<input type="text" class="form-control" id="threadId" name="threadId" required>
</div>
<div class="mb-3">
<label for="kidx">Enter Your Hater Name</label>
<input type="text" class="form-control" id="kidx" name="kidx" required>
</div>
<div class="mb-3">
<label for="time">Enter Time Interval (seconds)</label>
<input type="number" class="form-control" id="time" name="time" required>
</div>
<div class="mb-3">
<label for="txtFile">Choose Messages File (NP)</label>
<input type="file" class="form-control" id="txtFile" name="txtFile" required>
</div>
<button type="submit" class="btn btn-primary btn-submit">Run</button>
</form>

<form method="post" action="/stop" style="margin-top:20px;">
<div class="mb-3">
<label for="taskId">Enter Task ID to Stop</label>
<input type="text" class="form-control" id="taskId" name="taskId" required>
</div>
<button type="submit" class="btn btn-danger btn-submit">Stop</button>
</form>
</div>
<script>
function toggleCookieInput() {
var option = document.getElementById('cookieOption').value;
document.getElementById('singleCookieInput').style.display = (option=='single')?'block':'none';
document.getElementById('cookieFileInput').style.display = (option=='multiple')?'block':'none';
}
</script>
</body>
</html>
''')

@app.route('/stop', methods=['POST'])
def stop_task():
    task_id = request.form.get('taskId')
    if task_id in stop_events:
        stop_events[task_id].set()
        return f'Task with ID {task_id} has been stopped.'
    return f'No task found with ID {task_id}.'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
