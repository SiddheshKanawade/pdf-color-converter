from flask import Flask, render_template, request, send_from_directory, redirect, url_for, after_this_request, flash, abort, jsonify, make_response, send_file
import os
from io import BytesIO
from PIL import Image
import fitz
import json
import numpy as np
from datetime import datetime
import markdown
import yaml
import re
import csv
from functools import wraps
import time
from flask_compress import Compress
import tempfile
import random
import uuid
import secrets
import requests

# Import Vercel Blob for storage
import vercel_blob

from src.invert_color import invert_pdf_colors, remove_pages
from src.extract_data import extract_data_from_pdf

app = Flask(__name__, static_folder='static')
Compress(app)  # Enable compression properly using Flask-Compress
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(16))

# Configure file storage
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/tmp/uploads')
PROCESSED_FOLDER = os.environ.get('PROCESSED_FOLDER', '/tmp/processed')
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_FILE_SIZE', 10)) * 1024 * 1024  # Default 10MB
DEV_MODE = os.environ.get('DEV_MODE', 'false').lower() == 'true'
BLOB_EXPIRATION = int(os.environ.get('BLOB_EXPIRATION', 86400))  # Default 24 hours

# Create folders if they don't exist (for local development)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# Utility function to save an uploaded file to Vercel Blob Storage
async def save_uploaded_file(file, directory='uploads'):
    try:
        if file and file.filename:
            # Generate unique filename to avoid conflicts
            ext = os.path.splitext(file.filename)[1]
            unique_id = str(uuid.uuid4())
            unique_filename = f"{directory}/{unique_id}{ext}"
            
            # Read the file content
            file_content = file.read()
            
            # Determine the content type
            content_type = file.content_type or 'application/pdf'
            
            # Upload to Blob Storage
            result = await vercel_blob.put(
                unique_filename,
                file_content,
                options={
                    'access': 'public',
                    'contentType': content_type,
                    'addRandomSuffix': False
                }
            )
            
            return {"success": True, "filename": unique_filename, "url": result.url, "blob": result}
        else:
            return {"success": False, "error": "No file provided"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# Utility function to save content to Vercel Blob Storage
async def save_content_to_blob(content, filename, content_type='application/pdf', directory='outputs'):
    try:
        # Generate the full path including directory
        unique_id = str(uuid.uuid4())
        unique_filename = f"{directory}/{unique_id}_{filename}"
        
        # Upload to Blob Storage
        result = await vercel_blob.put(
            unique_filename,
            content,
            options={
                'access': 'public',
                'contentType': content_type,
                'addRandomSuffix': False
            }
        )
        
        return {"success": True, "filename": unique_filename, "url": result.url, "blob": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

# Utility function to retrieve file content (local or blob)
async def get_file_content(file_path_or_url):
    try:
        # For Blob URLs, use get
        if 'vercel-blob.com' in file_path_or_url:
            content = await vercel_blob.get(file_path_or_url)
            return BytesIO(content)
        else:
            # For local files
            with open(file_path_or_url, 'rb') as f:
                return BytesIO(f.read())
    except Exception as e:
        print(f"Error getting file content: {e}")
        return None

# Utility function to delete file (local or blob)
async def delete_file(file_path_or_url):
    try:
        # For Blob URLs, delete the blob
        if 'vercel-blob.com' in file_path_or_url:
            # Extract the path from the URL
            path = file_path_or_url.split('/')[-1].split('?')[0]
            await vercel_blob.delete(path)
            return True
        else:
            # For local files
            if os.path.exists(file_path_or_url):
                os.remove(file_path_or_url)
                return True
        return False
    except Exception as e:
        print(f"Error deleting file: {e}")
        return False

# Regular route cleanup for local files (not needed for Blob Storage as it auto-expires)
def cleanup_old_files():
    """Clean up files older than 24 hours in local storage directories."""
    if not DEV_MODE:
        return  # No need to clean up when using Blob Storage
        
    current_time = time.time()
    for directory in [UPLOAD_FOLDER, PROCESSED_FOLDER]:
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath) and (current_time - os.path.getmtime(filepath)) > 86400:
                try:
                    os.remove(filepath)
                    print(f"Cleaned up old file: {filepath}")
                except Exception as e:
                    print(f"Error cleaning up file {filepath}: {e}")

# Run cleanup periodically
@app.before_request
def before_request():
    # Run cleanup with 1% chance on each request to avoid doing it too often
    if DEV_MODE and random.random() < 0.01:
        cleanup_old_files()

# Configure temporary directories for processing
TEMP_FOLDER = tempfile.gettempdir()
os.makedirs(TEMP_FOLDER, exist_ok=True)

# Configure Blob storage access
BLOB_STORE_ID = os.environ.get('BLOB_STORE_ID')
BLOB_READ_WRITE_TOKEN = os.environ.get('BLOB_READ_WRITE_TOKEN')

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
async def remove():
    if 'file' not in request.files:
        return redirect(request.url)
    
    file = request.files['file']
    pages = request.form.get('pages', '')

    if file.filename == '':
        return redirect(request.url)

    if file and file.filename.endswith('.pdf'):
        try:
            # Create temporary files for processing
            temp_input_path = os.path.join(TEMP_FOLDER, f"input_{file.filename}")
            temp_output_path = os.path.join(TEMP_FOLDER, f"output_{file.filename}")
            
            # Save uploaded file temporarily
            file.save(temp_input_path)
            
            # Process the PDF (remove pages)
            remove_pages(temp_input_path, temp_output_path, pages)
            
            # Upload processed file to storage
            with open(temp_output_path, 'rb') as f:
                file_content = f.read()
            
            # Save the processed file
            blob_url = await save_processed_file(file_content, file.filename, 'application/pdf', 'removed_pages_')
            
            # Clean up temporary files
            os.remove(temp_input_path)
            os.remove(temp_output_path)
            
            # Return URL to download the processed file
            return redirect(url_for('download_redirect', blob_url=blob_url))
        except Exception as e:
            print(f"Error processing PDF: {e}")
            flash("An error occurred while processing your PDF", "error")
            return redirect(request.url)
    else:
        flash("Invalid file format. Please upload a PDF.", "error")
        return redirect(request.url)

@app.route('/upload', methods=['POST'])
async def upload_file():
    if 'file' not in request.files:
        flash("No file part", "error")
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        flash("No file selected", "error")
        return redirect(request.url)
        
    if file and file.filename.endswith('.pdf'):
        try:
            # Create temporary files for processing
            temp_input_path = os.path.join(TEMP_FOLDER, f"input_{file.filename}")
            temp_output_path = os.path.join(TEMP_FOLDER, f"output_{file.filename}")
            
            # Save uploaded file temporarily
            file.save(temp_input_path)
            
            # Process the file (invert colors)
            invert_pdf_colors(temp_input_path, temp_output_path)
            
            # Upload processed file to storage
            with open(temp_output_path, 'rb') as f:
                file_content = f.read()
            
            # Save the processed file
            blob_url = await save_processed_file(file_content, file.filename, 'application/pdf', 'inverted_')
            
            # Clean up temporary files
            os.remove(temp_input_path)
            os.remove(temp_output_path)
            
            # Return URL to download the processed file
            return redirect(url_for('download_redirect', blob_url=blob_url))
        except Exception as e:
            print(f"Error processing PDF: {e}")
            flash("An error occurred while processing your PDF", "error")
            return redirect(request.url)
    else:
        flash("Invalid file format. Please upload a PDF.", "error")
        return redirect(request.url)

@app.route('/download-redirect')
def download_redirect():
    """
    Handle redirects to blob URLs for file downloads.
    This is necessary to provide a better user experience when downloading files
    from Vercel Blob Storage.
    """
    blob_url = request.args.get('blob_url', '')
    if not blob_url:
        flash('No download URL provided', 'error')
        return redirect(url_for('index'))
    
    return render_template('download-redirect.html', blob_url=blob_url)

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
async def upload_for_redaction():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file:
        try:
            # Use our utility function to save to blob storage
            result = await save_uploaded_file(file, directory='redact_inputs')
            
            if not result["success"]:
                return jsonify({'error': result["error"]}), 500
                
            return jsonify({'success': True, 'filename': result["url"]})
        except Exception as e:
            print(f"Error in upload for redaction: {e}")
            return jsonify({'error': str(e)}), 500

@app.route('/apply-redactions', methods=['POST'])
async def apply_redactions():
    data = request.json
    blob_url = data.get('filename')
    redactions = data.get('redactions', [])
    
    if not blob_url or not redactions:
        return jsonify({'error': 'Missing filename or redactions'}), 400
    
    try:
        # Create temporary files for processing
        temp_input_filename = f"redact_input_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        temp_input_path = os.path.join(TEMP_FOLDER, temp_input_filename)
        
        temp_output_filename = f"redact_output_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        temp_output_path = os.path.join(TEMP_FOLDER, temp_output_filename)
        
        # Download file from Blob storage
        blob_data = await get_file_content(blob_url)
        if not blob_data:
            return jsonify({'error': 'Could not retrieve original file'}), 400
        
        # Save to temporary file
        with open(temp_input_path, 'wb') as f:
            f.write(blob_data.getvalue())
        
        # Apply redactions
        doc = fitz.open(temp_input_path)
        
        # Apply redactions to each page
        for redaction in redactions:
            page_num = redaction['page']
            x0, y0 = redaction['x'], redaction['y']
            x1, y1 = x0 + redaction['width'], y0 + redaction['height']
            
            if 0 <= page_num < doc.page_count:
                page = doc[page_num]
                page.add_redact_annot((x0, y0, x1, y1), fill=(0, 0, 0))
                page.apply_redactions()
        
        doc.save(temp_output_path)
        doc.close()
        
        # Upload redacted file to Vercel Blob
        original_filename = blob_url.split('/')[-1].split('?')[0]
        output_filename = f"redacted_{datetime.now().strftime('%Y%m%d%H%M%S')}_{original_filename}"
        
        with open(temp_output_path, 'rb') as f:
            blob = await vercel_blob.put(
                output_filename,
                f,
                options={
                    'access': 'public',
                    'addRandomSuffix': True
                }
            )
        
        # Clean up temporary files
        os.unlink(temp_input_path)
        os.unlink(temp_output_path)
        
        # Return success with URL
        return jsonify({'success': True, 'url': blob.url})
    
    except Exception as e:
        print(f"Error applying redactions: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/merge-pdf')
def merge_pdf_page():
    return render_template('merge.html')

@app.route('/merge-pdfs', methods=['POST'])
async def merge_pdfs():
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
            temp_path = os.path.join(TEMP_FOLDER, f"merge_input_{file.filename}")
            file.save(temp_path)
            temp_files.append(temp_path)
            
            # Open the PDF and append all pages to the merged document
            pdf_doc = fitz.open(temp_path)
            merged_doc.insert_pdf(pdf_doc)
            pdf_doc.close()
        
        # Save the merged document to a temporary file
        temp_output_path = os.path.join(TEMP_FOLDER, f"merged_output_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf")
        merged_doc.save(temp_output_path)
        merged_doc.close()
        
        # Upload merged file to Vercel Blob
        output_filename = f"merged_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        
        with open(temp_output_path, 'rb') as f:
            blob = await vercel_blob.put_blob(
                output_filename,
                f,
                vercel_blob.PutBlobOptions(access='public', addRandomSuffix=True)
            )
        
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
            except:
                pass
        os.remove(temp_output_path)
        
        return jsonify({'success': True, 'merged_filename': blob.url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/customize-colors')
def customize_colors_page():
    return render_template('customize_colors.html')

@app.route('/customize-pdf', methods=['POST'])
async def customize_pdf():
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
                
        # Create temporary files for processing
        temp_input_path = os.path.join(TEMP_FOLDER, f"customize_input_{file.filename}")
        temp_output_path = os.path.join(TEMP_FOLDER, f"customize_output_{file.filename}")
        
        # Save uploaded file to temp location
        file.save(temp_input_path)
        
        # Open the PDF
        doc = fitz.open(temp_input_path)
        
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
        doc.save(temp_output_path)
        doc.close()
        
        # Upload customized file to Vercel Blob
        output_filename = f"customized_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
        
        with open(temp_output_path, 'rb') as f:
            blob = await vercel_blob.put_blob(
                output_filename,
                f,
                vercel_blob.PutBlobOptions(access='public', addRandomSuffix=True)
            )
        
        # Clean up temporary files
        os.remove(temp_input_path)
        os.remove(temp_output_path)
        
        return jsonify({'success': True, 'filename': blob.url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/extract-data', methods=['GET'])
def extract_data_page():
    return render_template('extract-data.html')

@app.route('/extract-batch', methods=['POST'])
async def extract_batch():
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
        # Process PDFs and extract data
        extracted_data = []
        temp_files = []
        
        for file in files:
            # Save files temporarily
            temp_path = os.path.join(TEMP_FOLDER, f"extract_input_{file.filename}")
            file.save(temp_path)
            temp_files.append(temp_path)
            
            # Extract data from PDF
            data = extract_data_from_pdf(temp_path, fields_to_extract)
            extracted_data.append({
                'filename': file.filename,
                'data': data
            })
        
        # Create CSV from extracted data
        csv_filename = f"extracted_data_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
        csv_path = os.path.join(TEMP_FOLDER, csv_filename)
        
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
        
        # Upload CSV to Vercel Blob
        with open(csv_path, 'rb') as f:
            blob = await vercel_blob.put_blob(
                csv_filename,
                f,
                vercel_blob.PutBlobOptions(access='public', addRandomSuffix=True)
            )
        
        # Clean up temporary files
        for path in temp_files:
            try:
                os.remove(path)
            except:
                pass
        os.remove(csv_path)
        
        return jsonify({'success': True, 'csv_filename': blob.url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/extract-single', methods=['POST'])
async def extract_single():
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
        temp_path = os.path.join(TEMP_FOLDER, f"extract_single_{file.filename}")
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

# Create a context processor for static file URLs
@app.context_processor
def utility_processor():
    def versioned_url_for(endpoint, **values):
        # Add a version parameter for cache busting if needed
        if endpoint == 'static':
            values['v'] = '1'  # Change this version number when you update static files
            
            # Handle the case where Vercel might need a different path treatment
            # when _external=True is specified
            if values.get('_external', False) and 'VERCEL' in os.environ:
                # When in Vercel environment, make sure external URLs point to the right domain
                vercel_url = os.environ.get('VERCEL_URL', '')
                if vercel_url and not vercel_url.startswith(('http://', 'https://')):
                    vercel_url = f"https://{vercel_url}"
                return f"{vercel_url}/static/{values['filename']}?v={values['v']}"
        
        # For all other cases, use Flask's url_for
        return url_for(endpoint, **values)
    return dict(versioned_url_for=versioned_url_for)

@app.route('/invert-colors', methods=['POST'])
async def invert_colors():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file:
        try:
            # Create temporary file to work with
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                file.save(temp_file.name)
                temp_input_path = temp_file.name
            
            # Process the PDF (invert colors)
            temp_output_path = f"{temp_input_path}_inverted.pdf"
            invert_pdf_colors(temp_input_path, temp_output_path)
            
            # Generate output filename
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            output_filename = f"inverted_{timestamp}.pdf"
            
            # Upload to Vercel Blob
            with open(temp_output_path, 'rb') as f:
                blob = await vercel_blob.put(
                    output_filename,
                    f,
                    options={
                        'access': 'public',
                        'addRandomSuffix': True
                    }
                )
            
            # Clean up temporary files
            os.unlink(temp_input_path)
            os.unlink(temp_output_path)
            
            # Return success with URL
            return jsonify({"success": True, "url": blob.url})
        
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/remove-pages', methods=['POST'])
async def remove_pages_api():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    pages_to_remove = request.form.get('pages', '')
    
    if not pages_to_remove:
        return jsonify({"error": "No pages specified for removal"}), 400
    
    try:
        # Parse pages to remove
        pages_list = [int(p.strip()) for p in pages_to_remove.split(',') if p.strip().isdigit()]
        
        if not pages_list:
            return jsonify({"error": "Invalid page numbers"}), 400
        
        # Create temporary file to work with
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            file.save(temp_file.name)
            temp_input_path = temp_file.name
        
        # Process the PDF (remove pages)
        temp_output_path = f"{temp_input_path}_pages_removed.pdf"
        remove_pages(temp_input_path, temp_output_path, pages_list)
        
        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        output_filename = f"pages_removed_{timestamp}.pdf"
        
        # Upload to Vercel Blob
        with open(temp_output_path, 'rb') as f:
            blob = await vercel_blob.put(
                output_filename,
                f,
                options={
                    'access': 'public',
                    'addRandomSuffix': True
                }
            )
        
        # Clean up temporary files
        os.unlink(temp_input_path)
        os.unlink(temp_output_path)
        
        # Return success with URL
        return jsonify({"success": True, "url": blob.url})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/extract', methods=['POST'])
async def extract_data_api():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({"error": "File must be a PDF"}), 400
    
    try:
        # Create temporary file to work with
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            file.save(temp_file.name)
            temp_input_path = temp_file.name
        
        # Extract data from PDF
        data = extract_data_from_pdf(temp_input_path)
        
        # Save data to CSV
        csv_path = f"{temp_input_path}_data.csv"
        with open(csv_path, 'w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(['Page', 'Type', 'Text'])
            for item in data:
                csv_writer.writerow([item['page'], item['type'], item['text']])
        
        # Generate CSV filename
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        original_filename = os.path.splitext(file.filename)[0]
        csv_filename = f"{original_filename}_data_{timestamp}.csv"
        
        # Upload CSV to Vercel Blob
        with open(csv_path, 'rb') as f:
            blob = await vercel_blob.put(
                csv_filename,
                f,
                options={
                    'access': 'public', 
                    'addRandomSuffix': True
                }
            )
        
        # Clean up temporary files
        os.unlink(temp_input_path)
        os.unlink(csv_path)
        
        # Return success with URL and extracted data
        return jsonify({
            "success": True,
            "url": blob.url,
            "data": data
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
