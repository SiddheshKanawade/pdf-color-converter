/**
 * FAQ Accordion Functionality
 * This script handles the accordion behavior for FAQ sections across the site
 */
document.addEventListener('DOMContentLoaded', function() {
    // Add accordion functionality to FAQs
    const faqItems = document.querySelectorAll('.faq-item');
    
    faqItems.forEach(item => {
        const question = item.querySelector('.faq-question');
        
        question.addEventListener('click', () => {
            // Toggle current item
            item.classList.toggle('active');
            
            // Uncomment the below to enable accordion behavior (close other items)
            /*
            faqItems.forEach(otherItem => {
                if (otherItem !== item) {
                    otherItem.classList.remove('active');
                }
            });
            */
        });
    });
    
    // Open the first FAQ item by default
    if (faqItems.length > 0) {
        faqItems[0].classList.add('active');
    }
}); 