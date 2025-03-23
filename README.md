# PDF Color Converter

A web application for converting and manipulating PDF files, built with Flask and Vercel Blob Storage.

## Features

- Convert dark PDFs to light (color inversion)
- Redact sensitive information in PDFs
- Merge multiple PDFs into one document
- Customize PDF colors (create dark mode PDFs)
- Extract data from PDFs
- Remove pages from PDFs

## Getting Started

### Prerequisites

- Python 3.9+
- Vercel account for deployment
- Vercel Blob Storage for file handling

### Local Development

1. Clone the repository
   ```
   git clone https://github.com/yourusername/pdf-color-converter.git
   cd pdf-color-converter
   ```

2. Install dependencies
   ```
   pip install -r requirements.txt
   ```

3. Set up Vercel Blob Storage
   - Create a Vercel account if you don't have one
   - Install the Vercel CLI: `npm i -g vercel`
   - Create a new Vercel Blob Store:
     ```
     vercel login
     vercel link
     vercel env add BLOB_STORE_ID
     vercel env add BLOB_READ_WRITE_TOKEN
     ```

4. Set up your environment variables
   ```
   cp .env.example .env
   # Edit .env with your actual credentials
   ```

5. Run the development server
   ```
   python app.py
   ```

### Deployment to Vercel

1. Make sure you have the Vercel CLI installed and are logged in

2. Deploy the application
   ```
   vercel
   ```

3. To deploy to production
   ```
   vercel --prod
   ```

## Environment Variables

The following environment variables are required:

- `BLOB_STORE_ID`: Your Vercel Blob Store ID
- `BLOB_READ_WRITE_TOKEN`: Your Vercel Blob Store read/write token

## How Vercel Blob Storage is Used

This application uses Vercel Blob Storage to:

1. Store uploaded PDF files temporarily
2. Store processed PDF files for download
3. Handle file storage in a serverless-friendly way
4. Automatically clean up files after 24 hours

### Implementation Details

The app uses Vercel's Blob Storage instead of the local file system for several key reasons:

- **Serverless Compatibility**: Serverless functions have ephemeral filesystems that don't persist between invocations
- **Scalability**: Blob Storage can handle multiple concurrent uploads/downloads without issues
- **Security**: Files are stored securely with access controls
- **Auto-Cleanup**: Files are automatically removed after their expiration (24 hours by default)

We've implemented an adapter pattern to seamlessly work with Blob Storage:

1. When users upload files, they're stored in Blob Storage and URLs are returned
2. Processing functions work with file-like objects from Blob Storage
3. Download links point to Blob URLs with the appropriate content type
4. The `/download-redirect` endpoint handles smooth delivery of processed files

## License

[MIT](LICENSE)

## Acknowledgements

- [PyMuPDF](https://github.com/pymupdf/PyMuPDF) for PDF processing
- [Flask](https://flask.palletsprojects.com/) for the web framework
- [Vercel](https://vercel.com/) for hosting and Blob Storage 