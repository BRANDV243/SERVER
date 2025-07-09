from flask import Flask, request, render_template_string, flash, redirect, url_for
import pywhatkit as kit
import time
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WhatsApp Automation</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f0f8ff; /* Light blue background */
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }
        .container {
            background-color: #ffffff; /* White container */
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
            max-width: 400px;
            width: 100%;
        }
        h1 {
            text-align: center;
            color: #333; /* Dark gray text */
            margin-bottom: 20px;
        }
        label {
            display: block;
            font-weight: bold;
            margin: 10px 0 5px;
            color: #555; /* Medium gray labels */
        }
        input, button {
            width: 100%;
            padding: 10px;
            margin-bottom: 15px;
            border: 1px solid #ccc;
            border-radius: 5px;
            font-size: 16px;
        }
        input:focus, button:focus {
            outline: none;
            border-color: #4caf50; /* Green focus border */
            box-shadow: 0 0 5px rgba(76, 175, 80, 0.5); /* Green glow */
        }
        button {
            background-color: #4caf50; /* Green button */
            color: white;
            border: none;
            cursor: pointer;
            font-weight: bold;
        }
        button:hover {
            background-color: #45a049; /* Darker green */
        }
        .message {
            color: red;
            font-size: 14px;
            text-align: center;
        }
        .success {
            color: green;
            font-size: 14px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>WhatsApp Automation</h1>
        <form action="/" method="POST" enctype="multipart/form-data">
            <label for="sender_number">Your Mobile Number:</label>
            <input type="text" id="sender_number" name="sender_number" placeholder="Enter your WhatsApp number" required>

            <label for="target_number">Target Mobile Number:</label>
            <input type="text" id="target_number" name="target_number" placeholder="Enter target number (with country code)" required>

            <label for="txt_file">Message File:</label>
            <input type="file" id="txt_file" name="txt_file" accept=".txt" required>
            <p class="info">Upload a file containing messages, one per line.</p>

            <label for="delay">Delay (seconds):</label>
            <input type="number" id="delay" name="delay" placeholder="Enter delay in seconds" required>

            <button type="submit">Send Messages</button>
        </form>
    </div>
</body>
</html>
'''

# Route for handling requests
@app.route("/", methods=["GET", "POST"])
def whatsapp_automation():
    if request.method == "POST":
        try:
            # Get form data
            sender_number = request.form["sender_number"]
            target_number = request.form["target_number"]
            delay = int(request.form["delay"])

            # Save the uploaded TXT file
            txt_file = request.files["txt_file"]
            txt_file_path = os.path.join("uploaded_messages.txt")
            txt_file.save(txt_file_path)

            # Read messages from the file
            with open(txt_file_path, "r") as file:
                messages = file.readlines()

            # Start sending messages
            for message in messages:
                message = message.strip()
                if not message:
                    continue  # Skip empty lines
                
                print(f"[INFO] Sending message: {message}")
                kit.sendwhatmsg_instantly(target_number, message, 15, True, 5)
                print(f"[SUCCESS] Message sent: {message}")
                time.sleep(delay)

            # Cleanup
            os.remove(txt_file_path)

            flash("All messages sent successfully!", "success")
            return redirect(url_for("whatsapp_automation"))

        except Exception as e:
            flash(f"An error occurred: {e}", "error")
            return redirect(url_for("whatsapp_automation"))

    return render_template_string(HTML_TEMPLATE)

# Run the Flask app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
              
