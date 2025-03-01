from flask import Flask, render_template, request, send_from_directory, redirect, url_for, after_this_request
import os
from io import BytesIO
from PIL import Image
import fitz
import json
import numpy as np
from datetime import datetime
from flask import render_template_string
from flask import Flask, request, send_file, jsonify
import markdown
import yaml

from src.invert_color import invert_pdf_colors, remove_pages

app = Flask(__name__)

# Configure upload and processed directories
UPLOAD_FOLDER = '/tmp/uploads'
PROCESSED_FOLDER = '/tmp/processed'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 16MB max file size

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert')
def convert():
    return render_template('convert.html')

@app.route('/edit-pages')
def edit_pages():
    return render_template('remove.html')

@app.route("/upload_pdf", methods=["POST"])
def upload_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    return jsonify({"file_url": file_path})

@app.route("/redact", methods=["POST"])
def redact_pdf():
    if "file" not in request.files or "rects" not in request.form:
        return jsonify({"error": "Missing file or redaction data"}), 400

    file = request.files["file"]
    rects = json.loads(request.form["rects"])
    
    input_path = os.path.join(UPLOAD_FOLDER, file.filename)
    output_path = os.path.join(PROCESSED_FOLDER, f"redacted_{file.filename}")
    
    file.save(input_path)

    doc = fitz.open(input_path)
    page = doc[0]  # Assuming redaction is on the first page

    for rect in rects:
        x0, y0 = rect["x"], rect["y"]
        x1, y1 = x0 + rect["width"], y0 + rect["height"]
        page.add_redact_annot((x0, y0, x1, y1), fill=(0, 0, 0))  # Black redaction
        page.apply_redactions()

    doc.save(output_path)
    return send_file(output_path, as_attachment=True)

@app.route('/remove', methods=['POST'])
def remove():
    if 'file' not in request.files:
        return redirect(request.url)
    
    file = request.files['file']
    pages = request.form.get('pages', '')

    if file.filename == '':
        return redirect(request.url)

    if file and file.filename.endswith('.pdf'):
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        output_filename = f"processed_{file.filename}"
        output_path = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)

        file.save(input_path)

        remove_pages(input_path, output_path, pages)

        return redirect(url_for('download_file', filename=output_filename))
    else:
        return "Invalid file format. Please upload a PDF."

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)
    if file and file.filename.endswith('.pdf'):
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        output_filename = f"processed_{file.filename}"
        output_path = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)

        # Save the uploaded file
        file.save(input_path)

        # Process the file
        invert_pdf_colors(input_path, output_path)

        return redirect(url_for('download_file', filename=output_filename))
    else:
        return "Invalid file format. Please upload a PDF."

@app.route('/download/<filename>')
def download_file(filename):
    filepath = os.path.join(app.config['PROCESSED_FOLDER'], filename)

    @after_this_request
    def remove_file(response):
        try:
            os.remove(filepath)
        except Exception as e:
            app.logger.error(f"Error removing file {filepath}: {e}")
        return response

    return send_from_directory(app.config['PROCESSED_FOLDER'], filename, as_attachment=True)

@app.route('/blog')
def blog_index():
    with open('content/blog/posts.yaml', 'r') as file:
        posts = yaml.safe_load(file)
    return render_template('blog_index.html', posts=posts)

@app.route('/blog/<slug>')
def blog_post(slug):
    with open(f'content/blog/{slug}.md', 'r') as file:
        content = file.read()
    
    with open('content/blog/posts.yaml', 'r') as file:
        posts = yaml.safe_load(file)
        post = next((post for post in posts if post['slug'] == slug), None)
    
    if post is None:
        return redirect(url_for('blog_index'))
    
    post['content'] = markdown.markdown(content)
    return render_template('blog.html', post=post)

@app.route('/redact-pdf')
def redact_pdf_page():
    return render_template('redact.html')

@app.route('/upload-for-redaction', methods=['POST'])
def upload_for_redaction():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file:
        filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filename)
        return jsonify({'success': True, 'filename': file.filename})

@app.route('/apply-redactions', methods=['POST'])
def apply_redactions():
    data = request.json
    filename = data.get('filename')
    redactions = data.get('redactions', [])
    
    if not filename or not redactions:
        return jsonify({'error': 'Missing filename or redactions'}), 400
    
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    output_filename = f"redacted_{filename}"
    output_path = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)
    
    try:
        doc = fitz.open(input_path)
        
        # Apply redactions to each page
        for redaction in redactions:
            page_num = redaction['page']
            x0, y0 = redaction['x'], redaction['y']
            x1, y1 = x0 + redaction['width'], y0 + redaction['height']
            
            if 0 <= page_num < doc.page_count:
                page = doc[page_num]
                page.add_redact_annot((x0, y0, x1, y1), fill=(0, 0, 0))
                page.apply_redactions()
        
        doc.save(output_path)
        doc.close()
        
        return jsonify({'success': True, 'redacted_filename': output_filename})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
