import os
import re
import fitz
import json
from pathlib import Path
from mistralai import Mistral, DocumentURLChunk, ImageURLChunk, TextChunk
from mistralai.models import OCRResponse
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ["MISTRAL_API_KEY"]
client = Mistral(api_key=api_key)

def replace_images_in_markdown(markdown_str: str, images_dict: dict) -> str:
    """
    Replace image placeholders in markdown with base64-encoded images.

    Args:
        markdown_str: Markdown text containing image placeholders
        images_dict: Dictionary mapping image IDs to base64 strings

    Returns:
        Markdown text with images replaced by base64 data
    """
    for img_name, base64_str in images_dict.items():
        markdown_str = markdown_str.replace(
            f"![{img_name}]({img_name})", f"![{img_name}]({base64_str})"
        )
    return markdown_str

def get_combined_markdown(ocr_response: OCRResponse) -> str:
    """
    Combine OCR text and images into a single markdown document.

    Args:
        ocr_response: Response from OCR processing containing text and images

    Returns:
        Combined markdown string with embedded images
    """
    markdowns: list[str] = []
    # Extract images from page
    for page in ocr_response.pages:
        image_data = {}
        for img in page.images:
            image_data[img.id] = img.image_base64
        # Replace image placeholders with actual images
        markdowns.append(replace_images_in_markdown(page.markdown, image_data))

    return "\n\n".join(markdowns)

def get_ocr_response(pdf_file):
    pdf_file = Path(pdf_file)
    
    # Upload PDF file to Mistral's OCR service
    uploaded_file = client.files.upload(
        file={
            "file_name": pdf_file.stem,
            "content": pdf_file.read_bytes(),
        },
        purpose="ocr",
    )
    
    # Get URL for the uploaded file
    signed_url = client.files.get_signed_url(file_id=uploaded_file.id, expiry=1)

    # Process PDF with OCR, including embedded images
    pdf_response = client.ocr.process(
        document=DocumentURLChunk(document_url=signed_url.url),
        model="mistral-ocr-latest",
        include_image_base64=False
    )
    
    return pdf_response

def get_prompt_for_markdown(markdown, fields_to_extract=None):
    if fields_to_extract is None:
        return (
            f"This is document's OCR in markdown:\n\n{markdown}\n.\n"
            "Convert this into a sensible structured json response. "
            "The output should be strictly be json with no extra commentary"
        )
    else:
        return (
            f"This is document's OCR in markdown:\n\n{markdown}\n.\n"
            "Convert this into a sensible structured json response. "
            f"Extract the following fields: {', '.join(fields_to_extract)}"
            "If given fields are not present in the document, return an empty string for that field. "
            "The output should be strictly be json with no extra commentary"
        )

def jsonify_ocr_response(markdown, prompt):
    # Get structured response from model
    chat_response = client.chat.complete(
        model="ministral-8b-latest",
        messages=[
            {
                "role": "user",
                "content": [
                    TextChunk(
                        text=(
                            f"This is document's OCR in markdown:\n\n{markdown}\n.\n"
                            "Convert this into a sensible structured json response. "
                            "The output should be strictly be json with no extra commentary"
                        )
                    ),
                ],
            }
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    # Parse and return JSON response
    response_dict = json.loads(chat_response.choices[0].message.content)
    
    return response_dict

def extract_data_from_pdf(pdf_path, fields_to_extract=None):
    """
    Extract data from a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        fields_to_extract: List of field names to extract (if None, extract all detected fields)
    
    Returns:
        Dictionary containing extracted data
    """
    try:
        if fields_to_extract:
            print(f"Extracting data from {pdf_path} with fields_to_extract: {fields_to_extract}")
        else:
            print(f"Extracting data from {pdf_path} w/o fields_to_extract")
        ocr_response = get_ocr_response(pdf_path)
        combined_markdown = get_combined_markdown(ocr_response)
        prompt = get_prompt_for_markdown(combined_markdown, fields_to_extract)
        json_response = jsonify_ocr_response(combined_markdown, prompt=prompt)
        
        return json_response
    except Exception as e:
        print(f"Error extracting data from {pdf_path}: {str(e)}")
        return {}