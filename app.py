from flask import Flask, render_template, request, send_from_directory, redirect, url_for, after_this_request
import os
from io import BytesIO
from PIL import Image
import fitz
import json
import numpy as np
from datetime import datetime
from flask import render_template_string
from flask import Flask, request, send_file, jsonify, make_response
import markdown
import yaml
import re
import csv
from functools import wraps
import time
from flask_compress import Compress

from src.invert_color import invert_pdf_colors, remove_pages
from src.extract_data import extract_data_from_pdf

app = Flask(__name__)
Compress(app)  # Enable compression properly using Flask-Compress

# Configure upload and processed directories
UPLOAD_FOLDER = '/tmp/uploads'
PROCESSED_FOLDER = '/tmp/processed'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 16MB max file size

# Cache control for static assets
def cache_control(max_age):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            response = make_response(f(*args, **kwargs))
            response.headers['Cache-Control'] = f'public, max-age={max_age}'
            return response
        return decorated_function
    return decorator

@app.route('/')
@cache_control(3600)  # Cache for 1 hour
def index():
    return render_template('index.html')

@app.route('/convert')
@cache_control(3600)
def convert():
    return render_template('convert.html')

@app.route('/edit-pages')
@cache_control(3600)
def edit_pages():
    return render_template('remove.html')

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

@app.route('/merge-pdf')
def merge_pdf_page():
    return render_template('merge.html')

@app.route('/merge-pdfs', methods=['POST'])
def merge_pdfs():
    if 'files[]' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('files[]')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No files selected'}), 400
    
    # Check if all files are PDFs
    for file in files:
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'All files must be PDFs'}), 400
    
    try:
        # Create a new PDF document
        merged_doc = fitz.open()
        
        # Save each file temporarily and add to the merged document
        temp_files = []
        for file in files:
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(temp_path)
            temp_files.append(temp_path)
            
            # Open the PDF and append all pages to the merged document
            pdf_doc = fitz.open(temp_path)
            merged_doc.insert_pdf(pdf_doc)
            pdf_doc.close()
        
        # Save the merged document
        output_filename = f"merged_pdf_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        output_path = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)
        merged_doc.save(output_path)
        merged_doc.close()
        
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
            except:
                pass
        
        return jsonify({'success': True, 'merged_filename': output_filename})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/customize-colors')
def customize_colors_page():
    return render_template('customize_colors.html')

@app.route('/customize-pdf', methods=['POST'])
def customize_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'File must be a PDF'}), 400
    
    # Get color preferences
    bg_color = request.form.get('bg_color', '#000000')
    text_color = request.form.get('text_color', '#ffffff')
    
    # Validate hex color format
    hex_pattern = re.compile(r'^#(?:[0-9a-fA-F]{3}){1,2}$')
    if not hex_pattern.match(bg_color) or not hex_pattern.match(text_color):
        return jsonify({'error': 'Invalid color format'}), 400
    
    try:
        # Convert hex colors to RGB tuples
        bg_rgb = tuple(int(bg_color.lstrip('#')[i:i+2], 16) / 255 for i in (0, 2, 4))
        text_rgb = tuple(int(text_color.lstrip('#')[i:i+2], 16) / 255 for i in (0, 2, 4))
                
        # Save the uploaded file
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(input_path)
        
        # Create output filename
        output_filename = f"customized_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        output_path = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)
        
        # Open the PDF
        doc = fitz.open(input_path)
        
        # Process each page
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Create a rectangle covering the entire page
            rect = page.rect
            
            # Add a colored background
            page.draw_rect(rect, color=bg_rgb, fill=bg_rgb)
            
            # Get the text
            text_blocks = page.get_text("dict")["blocks"]
            
            # Define a list of fallback fonts that should be available in PyMuPDF
            fallback_fonts = ["helvetica", "times-roman", "courier"]
            
            # Draw text in the specified color
            for block in text_blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            # Extract text and position
                            text = span["text"]
                            origin = fitz.Point(span["origin"])
                            font_size = span["size"]
                            
                            # Try to use a fallback font instead of the original
                            # This avoids the "need font file or buffer" error
                            try:
                                # First try with helvetica as a safe default
                                page.insert_text(
                                    origin,
                                    text,
                                    fontsize=font_size,
                                    fontname="helvetica",
                                    color=text_rgb
                                )
                            except Exception as font_error:
                                # If that fails, try other fallback fonts
                                success = False
                                for font in fallback_fonts:
                                    if font == "helvetica":  # Already tried
                                        continue
                                    try:
                                        page.insert_text(
                                            origin,
                                            text,
                                            fontsize=font_size,
                                            fontname=font,
                                            color=text_rgb
                                        )
                                        success = True
                                        break
                                    except:
                                        continue
                                
                                # If all fallbacks fail, log the error but continue processing
                                if not success:
                                    print(f"Could not render text: {text}")
        
        # Save the modified PDF
        print("Saving the modified PDF")
        doc.save(output_path)
        doc.close()
        
        # Clean up the input file
        try:
            os.remove(input_path)
        except:
            pass
        
        return jsonify({'success': True, 'filename': output_filename})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/extract-data', methods=['GET'])
def extract_data_page():
    return render_template('extract-data.html')

@app.route('/extract-batch', methods=['POST'])
def extract_batch():
    if 'files[]' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('files[]')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No files selected'}), 400
    
    # Check if all files are PDFs
    for file in files:
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'All files must be PDFs'}), 400
    
    # Check total size limit (100MB)
    total_size = 0
    for file in files:
        file.seek(0, os.SEEK_END)
        total_size += file.tell()
        file.seek(0)
    
    if total_size > 100 * 1024 * 1024:  # 100MB in bytes
        return jsonify({'error': 'Total size exceeds 100MB limit'}), 400
    
    if len(files) > 100:
        return jsonify({'error': 'Maximum 100 PDFs allowed'}), 400
    
    # Get fields to extract (if specified)
    fields_to_extract = None
    if 'fields' in request.form and request.form['fields'].strip():
        fields_to_extract = [field.strip() for field in request.form['fields'].split(',')]
    
    try:
        # Create a temporary directory for processing
        temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"batch_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Save files temporarily
        file_paths = []
        for file in files:
            temp_path = os.path.join(temp_dir, file.filename)
            file.save(temp_path)
            file_paths.append(temp_path)
        
        # Process PDFs and extract data
        extracted_data = []
        for path in file_paths:
            # Extract data from PDF
            data = extract_data_from_pdf(path, fields_to_extract)
            extracted_data.append({
                'filename': os.path.basename(path),
                'data': data
            })
        
        # Create CSV from extracted data
        csv_filename = f"extracted_data_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
        csv_path = os.path.join(app.config['PROCESSED_FOLDER'], csv_filename)
        
        # Write CSV file
        with open(csv_path, 'w', newline='') as csvfile:
            # Determine all possible fields from all documents
            all_fields = set()
            for item in extracted_data:
                all_fields.update(item['data'].keys())
            
            fieldnames = ['filename'] + sorted(list(all_fields))
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for item in extracted_data:
                row = {'filename': item['filename']}
                row.update(item['data'])
                writer.writerow(row)
        
        # Clean up temporary files
        for path in file_paths:
            try:
                os.remove(path)
            except:
                pass
        try:
            os.rmdir(temp_dir)
        except:
            pass
        
        return jsonify({'success': True, 'csv_filename': csv_filename})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/extract-single', methods=['POST'])
def extract_single():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'File must be a PDF'}), 400
    
    # Check file size (45MB)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > 45 * 1024 * 1024:  # 45MB in bytes
        return jsonify({'error': 'File size exceeds 45MB limit'}), 400
    
    try:
        # Save file temporarily
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(temp_path)
        
        # Extract data from PDF
        data = extract_data_from_pdf(temp_path)
        
        # Clean up temporary file
        try:
            os.remove(temp_path)
        except:
            pass
        
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/sitemap.xml')
def sitemap():
    """Generate a dynamic sitemap"""
    host_base = request.host_url.rstrip('/')
    
    # Define static routes
    static_routes = [
        '',
        '/convert',
        '/edit-pages',
        '/redact-pdf',
        '/merge-pdf',
        '/customize-colors',
        '/extract-data',
        '/blog'
    ]
    
    # Get blog posts from content directory
    blog_posts = []
    content_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'content')
    if os.path.exists(content_dir):
        for filename in os.listdir(content_dir):
            if filename.endswith('.md'):
                slug = filename[:-3]  # Remove .md extension
                blog_posts.append(f'/blog/{slug}')
    
    # Combine all routes
    pages = []
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Add static routes
    for route in static_routes:
        pages.append({
            'loc': f'{host_base}{route}',
            'lastmod': today,
            'changefreq': 'weekly' if route in ['', '/blog'] else 'monthly',
            'priority': '1.0' if route == '' else '0.8'
        })
    
    # Add blog posts
    for route in blog_posts:
        pages.append({
            'loc': f'{host_base}{route}',
            'lastmod': today,
            'changefreq': 'monthly',
            'priority': '0.7'
        })
    
    sitemap_xml = render_template('sitemap.xml', pages=pages)
    response = make_response(sitemap_xml)
    response.headers['Content-Type'] = 'application/xml'
    return response

@app.route('/robots.txt')
def robots():
    return send_from_directory(app.static_folder, 'robots.txt')

# Add security headers without compression
@app.after_request
def add_header(response):
    # Add security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    return response

if __name__ == '__main__':
    app.run(debug=True)
