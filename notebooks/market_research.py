import pdfkit
from jinja2 import Environment, FileSystemLoader

# Set up Jinja2 environment
env = Environment(loader=FileSystemLoader('.'))
template = env.get_template('./notebooks/market_research.html')

# Render HTML with your dynamic title
businesses = ["Library", "Vending Machine", "Airbnb", "Saffron Farming", "Mineral Water Plant", "RO Water Plant", "Microgreen Farming", "Bitcoin Mining", "Coaching Institute", "Tshirtwear(B2B)", "Solar Farm", "Gym Diet Food", "Organic Supermarket", "Car - washing", "ATM business", "Cold Storage", "Pure Juice Factory", "White board markers", "Cottage Industry - Create packaging material, boxes", "Notebook making", "Aluminium Foil Manufacturing", "Tissue Paper Manufacturing", "Paver Block Manufacturing", "Non woven bag(Cotton bag)", "Coffee Cup Manufacturing", "Paper Plate Manufacturing", "Papad Making"]
for b in businesses:
    html_content = template.render(title=b)

    # Convert HTML to PDF
    pdfkit.from_string(html_content, f'./pdfs/{b}.pdf')
