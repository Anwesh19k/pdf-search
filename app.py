import os
import re
from flask import Flask, render_template_string, request, redirect, url_for, send_from_directory, flash
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'supersecretkey'  # Needed for flash messages

HTML = '''
<!doctype html>
<title>PDF Search App</title>
<h2>Upload PDFs and Search Their Content</h2>
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

{% if pdfs %}
  <h4>Uploaded PDFs:</h4>
  <ul>
    {% for pdf in pdfs %}
      <li><a href="{{ url_for('download_file', filename=pdf) }}">{{ pdf }}</a></li>
    {% endfor %}
  </ul>
  <form method=get action="/">
    <input type=text name=query placeholder="Type your search..." required>
    <input type=submit value=Search>
  </form>
{% endif %}

{% if results %}
  <h3>Results for: "{{ request.args.get('query', '') }}"</h3>
  <ul>
  {% for filename, snippet in results %}
    <li>
      <b>{{ filename }}</b>: ... {{ snippet|safe }} ...
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

def extract_text_from_pdfs(pdf_paths):
    text_data = []
    for pdf_path in pdf_paths:
        try:
            reader = PdfReader(os.path.join(UPLOAD_FOLDER, pdf_path))
            full_text = ""
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    full_text += t + "\n"
            text_data.append({"filename": pdf_path, "content": full_text})
        except Exception as e:
            print(f"Failed to extract from {pdf_path}: {e}")
    return text_data

def search_pdfs(text_data, query):
    results = []
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    for doc in text_data:
        for match in pattern.finditer(doc["content"]):
            start = max(0, match.start() - 80)
            end = match.end() + 80
            snippet = doc["content"][start:end].replace('\n', ' ')
            snippet = re.sub(pattern, r"<mark>\g<0></mark>", snippet)
            results.append((doc["filename"], snippet))
    return results

@app.route("/", methods=["GET"])
def index():
    pdfs = os.listdir(UPLOAD_FOLDER)
    results = None
    query = request.args.get('query', '').strip()
    if query and pdfs:
        text_data = extract_text_from_pdfs(pdfs)
        results = search_pdfs(text_data, query)
    return render_template_string(HTML, pdfs=pdfs, results=results)

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
    app.run(debug=True)
