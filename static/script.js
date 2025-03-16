// Lazy loading for images and below-the-fold content
document.addEventListener('DOMContentLoaded', function() {
    // Lazy load images
    const lazyImages = document.querySelectorAll('img[data-src]');
    const lazyLoadElements = document.querySelectorAll('.lazy-load');
    
    // Intersection Observer for lazy loading
    const lazyLoadObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                if (entry.target.tagName === 'IMG') {
                    entry.target.src = entry.target.dataset.src;
                    entry.target.removeAttribute('data-src');
                } else {
                    entry.target.classList.add('loaded');
                }
                observer.unobserve(entry.target);
            }
        });
    }, {
        rootMargin: '0px 0px 200px 0px'
    });
    
    // Observe all lazy load elements
    lazyImages.forEach(img => lazyLoadObserver.observe(img));
    lazyLoadElements.forEach(el => lazyLoadObserver.observe(el));
    
    // Handle form submissions with validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const fileInput = form.querySelector('input[type="file"]');
            if (fileInput && fileInput.files.length === 0) {
                e.preventDefault();
                alert('Please select a file to upload.');
                return false;
            }
            
            // Show loading indicator
            const submitButton = form.querySelector('button[type="submit"]');
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.innerHTML = '<span class="spinner"></span> Processing...';
            }
            
            return true;
        });
    });
    
    // Add aria-current to current page in navigation
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-links a');
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.setAttribute('aria-current', 'page');
        }
    });
});

// Improve page load performance
window.addEventListener('load', function() {
    // Preload critical resources for next pages
    const preloadLinks = [
        '/convert',
        '/redact-pdf',
        '/merge-pdf',
        '/customize-colors',
        '/extract-data'
    ];
    
    // Only preload if on homepage
    if (window.location.pathname === '/') {
        setTimeout(() => {
            preloadLinks.forEach(link => {
                const preloadLink = document.createElement('link');
                preloadLink.rel = 'prefetch';
                preloadLink.href = link;
                document.head.appendChild(preloadLink);
            });
        }, 2000); // Delay preloading to prioritize current page resources
    }
});

// Handle file uploads with drag and drop
document.addEventListener('DOMContentLoaded', function() {
    const dropAreas = document.querySelectorAll('.file-upload-area, .upload-prompt');
    
    dropAreas.forEach(area => {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            area.addEventListener(eventName, preventDefaults, false);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        ['dragenter', 'dragover'].forEach(eventName => {
            area.addEventListener(eventName, highlight, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            area.addEventListener(eventName, unhighlight, false);
        });
        
        function highlight() {
            area.classList.add('dragover');
        }
        
        function unhighlight() {
            area.classList.remove('dragover');
        }
        
        area.addEventListener('drop', handleDrop, false);
        
        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            const fileInput = area.querySelector('input[type="file"]');
            
            if (fileInput) {
                fileInput.files = files;
                // Trigger change event
                const event = new Event('change', { bubbles: true });
                fileInput.dispatchEvent(event);
            }
        }
    });
}); 