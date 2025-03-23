import os
import sys
import asyncio
from dotenv import load_dotenv
import vercel_blob

# Load environment variables from .env
load_dotenv()

# Check environment variables
blob_store_id = os.environ.get('BLOB_STORE_ID')
blob_token = os.environ.get('BLOB_READ_WRITE_TOKEN')

if not blob_store_id or not blob_token:
    print("ERROR: Missing Vercel Blob credentials.")
    print("Make sure BLOB_STORE_ID and BLOB_READ_WRITE_TOKEN are set in your .env file.")
    sys.exit(1)

async def test_blob_storage():
    print("Testing Vercel Blob Storage...")
    
    # Create a test file
    test_content = b"This is a test file for Vercel Blob storage."
    test_filename = "test_file.txt"
    
    try:
        # Upload the test file
        print(f"Uploading test file '{test_filename}'...")
        result = await vercel_blob.put(
            test_filename,
            test_content,
            options={'access': 'public'}
        )
        
        print(f"File uploaded successfully!")
        print(f"URL: {result.url}")
        
        # Get the file
        print("Downloading file...")
        content = await vercel_blob.get(result.url)
        
        if content == test_content:
            print("Content verified successfully!")
        else:
            print("ERROR: Downloaded content does not match uploaded content.")
        
        # List blobs
        print("Listing blobs...")
        blobs = await vercel_blob.list()
        print(f"Found {len(blobs.blobs)} blobs.")
        
        # Delete the file
        print("Deleting file...")
        await vercel_blob.delete(test_filename)
        print("File deleted successfully!")
        
        print("\nVercel Blob Storage test completed successfully!")
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_blob_storage()) 