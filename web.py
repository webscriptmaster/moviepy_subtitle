import os
import uuid
import datetime
from flask import Flask, render_template_string, request, send_from_directory
from threading import Thread
import shutil

app = Flask(__name__)

def generate_unique_id():
    return str(uuid.uuid4())

def generate_datetime_alias():
    current_time = datetime.datetime.now()
    return current_time.strftime("%Y-%m-%d_%H-%M-%S")

@app.route('/')
def index():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Scene Optimisation Bot</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f2f2f2;
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
            }
            .container {
                background-color: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                width: 400px;
                text-align: center;
            }
            h1 {
                color: #333;
            }
            input[type="file"] {
                margin-bottom: 10px;
            }
            input[type="submit"] {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
            }
            input[type="submit"]:hover {
                background-color: #45a049;
            }
            #waitMessage {
                margin-top: 20px;
                color: #555;
            }
        </style>
        <script>
            function displayMessage() {
                document.getElementById("waitMessage").innerText = "Please wait for files uploading process. Don't close the page.";
            }
            function downloadAll() {
                // Get all file names
                var files = [
                    {% for file in files %}
                        "{{ file }}",
                    {% endfor %}
                ];

                // Create a temporary anchor element
                var link = document.createElement("a");

                // Loop through each file and trigger download
                files.forEach(function(file) {
                    // Set the href attribute of the anchor element
                    link.setAttribute("href", "/download/" + file);
                    // Set the download attribute to force download
                    link.setAttribute("download", file);
                    // Simulate click on the anchor element
                    link.click();
                });
            }
        </script>
    </head>
    <body>
        <div class="container">
            <h1>Scene Optimisation Bot</h1>
            <form action="/process" method="post" enctype="multipart/form-data" onsubmit="displayMessage()">
                Video File <input type="file" name="video_file" required><br>
                Clips (zip) <input type="file" name="clips_folder" required><br>
                MP3 File <input type="file" name="mp3_file" required><br>
                Text File <input type="file" name="text_file" required><br>
                <input type="submit" value="Process">
            </form>
            <h1 id="waitMessage"></h1>
        </div>
    </body>
    </html>
    ''')

def remove_all_files_in_directory(directory):
    try:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.remove(file_path)
                    print(f"Removed file {file_path}")
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                    print(f"Removed directory {file_path}")
        else:
            print(f"Directory {directory} does not exist")
    except Exception as e:
        print(f"An error occurred: {e}")

@app.route('/process', methods=['POST'])
def process():
    static_out_file_server = os.path.join('static', 'output_root')
    tmp = os.path.join(os.getcwd(), 'tmp')
    final_out_path = os.path.join('static', 'output_root', 'final')
    outpath = os.path.join(static_out_file_server, f'output')
    
    try:
        remove_all_files_in_directory(f"{os.path.join(outpath, 'videos')}")
        remove_all_files_in_directory(f"{os.path.join(outpath, 'audios')}")
        remove_all_files_in_directory(final_out_path)
        tmp_dirs = os.listdir(tmp)
        for dir in tmp_dirs:
            remove_all_files_in_directory(os.path.join(tmp, dir))
        remove_all_files_in_directory(tmp)
    except:
        pass
    
    try:
        os.makedirs(outpath)
        os.makedirs(f"{os.path.join(outpath, 'audios')}")
        os.makedirs(f"{os.path.join(outpath, 'videos')}")
        os.makedirs(f"{os.path.join('static', 'output_root', 'final')}")
    except:
        pass
    
    unique_special_id = os.path.join('tmp', generate_unique_id())
    
    video_dir = os.path.join(unique_special_id, "video")
    clips_dir = os.path.join(unique_special_id, "clips")
    mp3_dir = os.path.join(unique_special_id, "mp3")
    text_dir = os.path.join(unique_special_id, "text")
    os.makedirs(video_dir, exist_ok=True)
    os.makedirs(clips_dir, exist_ok=True)
    os.makedirs(mp3_dir, exist_ok=True)
    os.makedirs(text_dir, exist_ok=True)

    video_file = request.files['video_file']
    video_file_path = os.path.join(video_dir, video_file.filename)
    video_file.save(video_file_path)

    clips_folder = request.files['clips_folder']
    clips_folder_path = os.path.join(clips_dir, clips_folder.filename)
    clips_folder.save(clips_folder_path)
    
    mp3_file = request.files['mp3_file']
    mp3_file_path = os.path.join(mp3_dir, mp3_file.filename)
    mp3_file.save(mp3_file_path)
    
    text_file = request.files['text_file']
    text_file_path = os.path.join(text_dir, text_file.filename)
    text_file.save(text_file_path)
    
    shutil.unpack_archive(clips_folder_path, clips_dir)
    
    def run_script():
        cmd = f'python3.10 test.py --input_video "{video_file_path}" --input_clips "{clips_dir}" --input_mp3 "{mp3_file_path}" --input_txt "{text_file_path}" --output_dir "{final_out_path}"'
        print(cmd)
        os.system(cmd)
    
    Thread(target=run_script).start()

    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Processing</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f2f2f2;
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
            }
            .
        container {
                background-color: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                width: 400px;
                text-align: center;
            }
            h1 {
                color: #333;
            }
            a {
                text-decoration: none;
                color: #4CAF50;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Uploaded Successfully</h1><br>
            <h1>Now click Download to access the files </h1>
            <a href="/download">Download <---</a>
        </div>
    </body>
    </html>
    ''')

@app.route('/download/')
def download():
    files = os.listdir('static/output_root/final')
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Download Files</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f2f2f2;
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
            }
            .container {
                background-color: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                width: 400px;
                text-align: center;
            }
            h1, h3 {
                color: #333;
            }
            ul {
                list-style-type: none;
                padding: 0;
            }
            li {
                margin: 5px 0;
            }
            a {
                text-decoration: none;
                color: #4CAF50;
                font-weight: bold;
            }
            .download-all-btn {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                margin-top: 20px;
            }
            .download-all-btn:hover {
                background-color: #45a049;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Available Files</h1><br>
            <h3>Note:</h3><br>
            <p>Keep refreshing the page, it will show the generated files. Download your file from here.</p>
            <ul id="fileList">
                {% for file in files %}
                <li><a href="{{ url_for('download_file', filename=file) }}">{{ file }}</a></li>
                {% endfor %}
            </ul>
            <button class="download-all-btn" onclick="downloadAll()">Download All</button>
        </div>

        <script>
            function downloadAll() {
                // Get all file names
                var files = [
                    {% for file in files %}
                        "{{ file }}",
                    {% endfor %}
                ];

                // Create a temporary anchor element
                var link = document.createElement("a");

                // Loop through each file and trigger download
                files.forEach(function(file) {
                    // Set the href attribute of the anchor element
                    link.setAttribute("href", "/download/" + file);
                    // Set the download attribute to force download
                    link.setAttribute("download", file);
                    // Simulate click on the anchor element
                    link.click();
                });
            }
        </script>
    </body>
    </html>
    ''', files=files)

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory('static/output_root/final', filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0')

