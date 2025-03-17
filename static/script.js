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
    
    // Handle file input changes
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(input => {
        input.addEventListener('change', function(e) {
            const fileName = e.target.files[0]?.name || 'No file selected';
            const fileNameElement = input.closest('.file-upload-container')?.querySelector('.file-name');
            
            if (fileNameElement) {
                fileNameElement.textContent = fileName;
                if (e.target.files.length > 0) {
                    fileNameElement.classList.add('selected');
                } else {
                    fileNameElement.classList.remove('selected');
                }
            }
        });
    });
    
    // Handle file upload drag and drop
    const fileUploadContainers = document.querySelectorAll('.file-upload-container');
    fileUploadContainers.forEach(container => {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            container.addEventListener(eventName, preventDefaults, false);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        ['dragenter', 'dragover'].forEach(eventName => {
            container.addEventListener(eventName, highlight, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            container.addEventListener(eventName, unhighlight, false);
        });
        
        function highlight() {
            container.classList.add('dragover');
        }
        
        function unhighlight() {
            container.classList.remove('dragover');
        }
        
        container.addEventListener('drop', handleDrop, false);
        
        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            const fileInput = container.querySelector('input[type="file"]');
            
            if (fileInput) {
                fileInput.files = files;
                // Trigger change event
                const event = new Event('change', { bubbles: true });
                fileInput.dispatchEvent(event);
            }
        }
    });
    
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
    
    // Handle search functionality
    const searchInput = document.querySelector('.search-input');
    if (searchInput) {
        searchInput.addEventListener('input', function(e) {
            const searchTerm = e.target.value.toLowerCase();
            const toolCards = document.querySelectorAll('.tool-card');
            
            toolCards.forEach(card => {
                const title = card.querySelector('h3').textContent.toLowerCase();
                const description = card.querySelector('p').textContent.toLowerCase();
                
                if (title.includes(searchTerm) || description.includes(searchTerm)) {
                    card.style.display = 'flex';
                } else {
                    card.style.display = 'none';
                }
            });
            
            // Show message if no results
            const toolsGrid = document.querySelector('.tools-grid');
            let visibleCards = 0;
            
            toolCards.forEach(card => {
                if (card.style.display !== 'none') {
                    visibleCards++;
                }
            });
            
            const noResultsMessage = document.querySelector('.no-results-message');
            
            if (visibleCards === 0 && searchTerm !== '') {
                if (!noResultsMessage) {
                    const message = document.createElement('div');
                    message.className = 'no-results-message';
                    message.textContent = 'No tools found matching your search.';
                    toolsGrid.appendChild(message);
                }
            } else if (noResultsMessage) {
                noResultsMessage.remove();
            }
        });
    }
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

// Add spinner styles
const style = document.createElement('style');
style.textContent = `
.spinner {
    display: inline-block;
    width: 1rem;
    height: 1rem;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-radius: 50%;
    border-top-color: white;
    animation: spin 1s ease-in-out infinite;
    margin-right: 0.5rem;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}
`;
document.head.appendChild(style); 