import os
import re
from flask import Flask, render_template_string, request, redirect, url_for, send_from_directory, flash
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'supersecretkey'

HTML = '''
<!doctype html>
<title>Q&A TXT Search App</title>
<h2>Upload TXT files (with Q&A) and Search Their Content</h2>
<form method=post enctype=multipart/form-data action="/upload">
  <input type=file name=file multiple required>
  <input type=submit value=Upload>
</form>
{% with messages = get_flashed_messages() %}
  {% if messages %}
    <ul>
    {% for message in messages %}
      <li style="color:red">{{ message }}</li>
    {% endfor %}
    </ul>
  {% endif %}
{% endwith %}

{% if files %}
  <h4>Uploaded TXT files:</h4>
  <ul>
    {% for f in files %}
      <li><a href="{{ url_for('download_file', filename=f) }}">{{ f }}</a></li>
    {% endfor %}
  </ul>
  <form method=get action="/">
    <input type=text name=query placeholder="Type your search..." required>
    <input type=submit value=Search>
  </form>
{% endif %}

{% if results is not none %}
  <h3>Results for: "{{ request.args.get('query', '') }}"</h3>
  <ul>
  {% for filename, q, a in results %}
    <li>
      <b>{{ filename }}</b>:<br>
      <b>Q:</b> {{ q|safe }}<br>
      <b>A:</b> {{ a|safe }}
      <br>
    </li>
  {% endfor %}
  </ul>
  {% if not results %}
    <p>No results found.</p>
  {% endif %}
{% endif %}
'''

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_qa_pairs(txt_paths):
    qa_data = []
    for txt_path in txt_paths:
        try:
            with open(os.path.join(UPLOAD_FOLDER, txt_path), encoding="utf-8") as f:
                content = f.read()
            # Find all Q&A pairs (assuming blank lines or consistent structure)
            pairs = re.findall(r"Q:(.*?)[\r\n]+A:(.*?)(?:[\r\n]+|$)", content, re.DOTALL | re.IGNORECASE)
            for q, a in pairs:
                qa_data.append({"filename": txt_path, "q": q.strip(), "a": a.strip()})
        except Exception as e:
            print(f"Failed to extract from {txt_path}: {e}")
    return qa_data

def search_qa(qa_data, query):
    results = []
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    for qa in qa_data:
        if pattern.search(qa["q"]) or pattern.search(qa["a"]):
            q_highlight = pattern.sub(r"<mark>\g<0></mark>", qa["q"])
            a_highlight = pattern.sub(r"<mark>\g<0></mark>", qa["a"])
            results.append((qa["filename"], q_highlight, a_highlight))
    return results

@app.route("/", methods=["GET"])
def index():
    files = [f for f in os.listdir(UPLOAD_FOLDER) if f.lower().endswith('.txt')]
    results = None
    query = request.args.get('query', '').strip()
    if query and files:
        qa_data = extract_qa_pairs(files)
        results = search_qa(qa_data, query)
    return render_template_string(HTML, files=files, results=results)

@app.route("/upload", methods=["POST"])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('index'))
    files = request.files.getlist('file')
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        else:
            flash('Invalid file format!')
    return redirect(url_for('index'))

@app.route('/uploads/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
