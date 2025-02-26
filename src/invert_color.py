from io import BytesIO
from PIL import Image
import pymupdf
import numpy as np


def invert_pdf_colors(input_pdf_path, output_pdf_path):
    try:
        document = pymupdf.open(input_pdf_path)
        new_pdf = pymupdf.open()
        
        # Increase Image Resolution
        mat = pymupdf.Matrix(2, 2) # zoom x, zoom y
        
        for page in document:
            pix = page.get_pixmap(matrix=mat)
            inverted_image = invert_image_colors(pix)
            
            buffer = BytesIO()
            inverted_image.save(buffer, format="PNG", quality=150)
            buffer.seek(0)
            
            rect = page.rect
            new_page = new_pdf.new_page(width=rect.width, height=rect.height)
            new_page.insert_image(rect, stream=buffer.read())
        
        new_pdf.save(output_pdf_path)
        new_pdf.close()
        document.close()
        return True
    except Exception as e:
        print(f"Error processing PDF: {e}")
        return False

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


def remove_pages(input_pdf, output_pdf, pages_to_remove):
    if '-' in pages_to_remove:
        start, end = pages_to_remove.split('-')
        pages_to_remove = range(int(start), int(end) + 1)
    else:
        pages_to_remove = [int(p) for p in pages_to_remove.split(',')]
        
    pages_to_remove = [p - 1 for p in pages_to_remove]  # Convert to 0-based indexing
    
    doc = pymupdf.open(input_pdf)
    
    # Delete pages (PyMuPDF uses 0-based indexing)
    for page_num in sorted(pages_to_remove, reverse=True):
        if 0 <= page_num < len(doc):
            doc.delete_page(page_num)

    # Save the modified PDF
    doc.save(output_pdf)
    doc.close()