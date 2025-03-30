#!/usr/bin/env python3
"""
Script to generate a static sitemap.xml file for pdfinverter.com
Run this script directly to generate the sitemap without starting the server.
"""

from flask import Flask, render_template
from datetime import datetime
import os
import sys
import importlib.util

def generate_sitemap_data_fallback(host_base=None):
    """Fallback implementation if import fails"""
    if not host_base:
        host_base = 'https://www.pdfinverter.com'
    
    # Define all accessible pages
    static_routes = [
        '',                  # Home page
        '/convert',          # Convert page
        '/edit-pages',       # Edit pages
        '/redact-pdf',       # Redact PDF tool
        '/merge-pdf',        # Merge PDF tool
        '/customize-colors', # Customize colors tool
        '/extract-data',     # Extract data tool
        '/blog'              # Blog index
    ]
    
    # Get blog posts from content directory
    blog_posts = []
    content_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'content', 'blog')
    if os.path.exists(content_dir):
        for filename in os.listdir(content_dir):
            if filename.endswith('.md') and filename != 'posts.yaml':
                slug = filename[:-3]  # Remove .md extension
                blog_posts.append(f'/blog/{slug}')
    
    # Combine all routes
    pages = []
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Add static routes with appropriate priorities
    for route in static_routes:
        priority = '1.0' if route == '' else '0.9' if route == '/convert' else '0.8'
        changefreq = 'weekly' if route in ['', '/convert', '/blog'] else 'monthly'
        
        pages.append({
            'loc': f'{host_base}{route}',
            'lastmod': today,
            'changefreq': changefreq,
            'priority': priority
        })
    
    # Add blog posts
    for route in blog_posts:
        pages.append({
            'loc': f'{host_base}{route}',
            'lastmod': today,
            'changefreq': 'monthly',
            'priority': '0.7'
        })
    
    return pages

def main():
    """Generate a static sitemap.xml file"""
    # Set up Flask app context for rendering templates
    app = Flask(__name__, template_folder='templates')
    
    with app.app_context():
        # Try to import the sitemap utility function from app.py
        try:
            # Try to load app.py as a module
            spec = importlib.util.spec_from_file_location("app", "app.py")
            if spec and spec.loader:
                app_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(app_module)
                # Use the imported function
                pages, sitemap_xml = app_module.generate_sitemap_data()
                print("Using generate_sitemap_data from app.py")
            else:
                raise ImportError("Could not load app.py module")
        except (ImportError, AttributeError) as e:
            print(f"Warning: {e}")
            print("Using fallback implementation for sitemap generation")
            
            # Use the fallback implementation
            pages = generate_sitemap_data_fallback()
            sitemap_xml = render_template('sitemap.xml', pages=pages)
        
        # Save to static file
        static_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
        with open(os.path.join(static_folder, 'sitemap.xml'), 'w') as f:
            f.write(sitemap_xml)
        
        print(f"✓ Static sitemap.xml generated with {len(pages)} URLs")
        print(f"  Location: {os.path.join(static_folder, 'sitemap.xml')}")

if __name__ == "__main__":
    main() 