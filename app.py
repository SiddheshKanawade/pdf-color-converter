from flask import Flask, render_template, request, send_from_directory, redirect, url_for
import os
from io import BytesIO
from PIL import Image
from flask import after_this_request
import fitz  # PyMuPDF
import numpy as np

app = Flask(__name__)

# Configure upload and processed directories
UPLOAD_FOLDER = '/tmp/uploads'
PROCESSED_FOLDER = '/tmp/processed'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

def invert_pdf_colors(input_pdf_path, output_pdf_path, jpeg_quality=75):
    """
    Inverts colors of a PDF to create a lighter version and reduces file size using JPEG compression.
    :param input_pdf_path: Path to the input PDF with dark background.
    :param output_pdf_path: Path where the output PDF will be saved.
    :param jpeg_quality: Quality for JPEG compression (1 to 100, higher means better quality and larger file size).
    """
    document = fitz.open(input_pdf_path)
    new_pdf = fitz.open()

    for page_number in range(len(document)):
        page = document[page_number]
        pix = page.get_pixmap()

        # Convert to inverted image
        inverted_image = invert_image_colors(pix)

        # Save the inverted image to a buffer in JPEG format
        buffer = BytesIO()
        inverted_image.save(buffer, format="JPEG", quality=jpeg_quality)
        buffer.seek(0)

        # Create a new page and insert the JPEG image
        rect = page.rect
        new_page = new_pdf.new_page(width=rect.width, height=rect.height)
        new_page.insert_image(rect, stream=buffer.read())

    new_pdf.save(output_pdf_path)
    new_pdf.close()
    document.close()

def invert_image_colors(pixmap):
    """
    Inverts the colors of an image.
    :param pixmap: A PyMuPDF Pixmap object.
    :return: A PIL Image object with inverted colors.
    """
    image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
    img_array = np.array(image)
    inverted_array = 255 - img_array
    return Image.fromarray(inverted_array.astype('uint8'))

@app.route('/')
def index():
    return render_template('index.html')

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

if __name__ == '__main__':
    app.run(debug=True)
