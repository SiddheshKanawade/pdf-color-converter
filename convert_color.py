import os
import fitz  # PyMuPDF
from io import BytesIO
from PIL import Image
import numpy as np
from glob import glob

def invert_pdf_colors(input_pdf_path, output_pdf_path):
    """
    Inverts colors of a PDF to create a lighter version.
    :param input_pdf_path: Path to the input PDF with dark background.
    :param output_pdf_path: Path where the output PDF will be saved.
    """
    # Open the original PDF
    document = fitz.open(input_pdf_path)
    
    # Create a new PDF
    new_pdf = fitz.open()

    for page_number in range(len(document)):
        page = document[page_number]
        pix = page.get_pixmap()  # Render page as an image

        # Convert to inverted image
        inverted_image = invert_image_colors(pix)

        # Save the inverted image to a buffer in PNG format
        buffer = BytesIO()
        inverted_image.save(buffer, format="JPEG")
        buffer.seek(0)

        # Create a new page and insert the inverted image
        rect = page.rect
        new_page = new_pdf.new_page(width=rect.width, height=rect.height)
        new_page.insert_image(rect, stream=buffer.read())

    # Save the updated PDF
    new_pdf.save(output_pdf_path)
    new_pdf.close()
    document.close()
    print(f"Lighter version saved as {output_pdf_path}")

def invert_image_colors(pixmap):
    """
    Inverts the colors of an image.
    :param pixmap: A PyMuPDF Pixmap object.
    :return: A PIL Image object with inverted colors.
    """
    # Convert Pixmap to PIL image
    image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
    img_array = np.array(image)

    # Invert colors
    inverted_array = 255 - img_array

    # Convert back to PIL image
    return Image.fromarray(inverted_array.astype('uint8'))

source_dir = "./dark_pdfs"
output_dir = "./light_pdfs"

os.makedirs(output_dir, exist_ok=True)

for pdf_path in glob(f"{source_dir}/*.pdf"):
    file_name = pdf_path.split("/")[-1]
    
    # Create the output path
    output_path = f"{output_dir}/{file_name}"
    invert_pdf_colors(pdf_path, output_path)