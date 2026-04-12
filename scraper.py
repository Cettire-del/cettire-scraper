import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

URL = "https://www.cettire.com/de/pages/search?qTitle=golden%20goose%20sneakers&menu%5Bdepartment%5D=men&menu%5Bproduct_type%5D=Sneakers&from=home.search_box_direct_query&query=golden%20goose%20sneakers&refinementList%5Btags%5D%5B0%5D=Shoes&refinementList%5BColor%5D=&refinementList%5Bvendor%5D=&refinementList%5BSize%5D%5B0%5D=US7&refinementList%5BSize%5D%5B1%5D=UK6&refinementList%5BSize%5D%5B2%5D=IT40&refinementList%5BSize%5D%5B3%5D=EU40&refinementList%5BSize%5D%5B4%5D=BR38&refinementList%5BSize%5D%5B5%5D=KR250&refinementList%5BSize%5D%5B6%5D=JP25&refinementList%5BSize%5D%5B7%5D=FR41&refinementList%5BSize%5D%5B8%5D=US8&refinementList%5BSize%5D%5B9%5D=UK7&refinementList%5BSize%5D%5B10%5D=IT41&refinementList%5BSize%5D%5B11%5D=EU41&refinementList%5BSize%5D%5B12%5D=BR39&refinementList%5BSize%5D%5B13%5D=KR260&refinementList%5BSize%5D%5B14%5D=JP26&refinementList%5BSize%5D%5B15%5D=FR42&page=1"

# Environment variables for email
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD") # Gmail App Password
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER") or EMAIL_SENDER

JSON_FILE = "known_listings.json"

def send_email(new_items):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("Email credentials not set. Skipping email.")
        return

    subject = f"Cettire Alert: {len(new_items)} New Golden Goose Sneakers Found!"
    
    html_body = "<h2>New Sneakers Found:</h2><ul>"
    for item in new_items:
        html_body += f"<li><a href='{item['url']}'><b>View Item</b></a>: {item['text']}</li>"
    html_body += "</ul>"

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

def main():
    known_urls = set()
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r") as f:
                known_list = json.load(f)
                known_urls = set(known_list)
        except:
            pass

    print("Launching browser...")
    with sync_playwright() as p:
        # Launching headless browser
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        print("Navigating to Cettire...")
        # High timeout because it can take a bit to render products
        page.goto(URL, timeout=60000)
        
        # Wait a few seconds for any dynamic JS elements and the products grid to load completely
        page.wait_for_timeout(8000) 
        
        # Scroll down slightly to trigger lazy-loaded images or content if necessary
        page.evaluate("window.scrollBy(0, 1000);")
        page.wait_for_timeout(2000)

        # Extract links that go to product pages
        print("Extracting products...")
        products = page.evaluate('''() => {
            const items = [];
            // Assuming Cettire product URLs contain '/products/' or similar.
            document.querySelectorAll('a').forEach(a => {
                if (a.href && a.href.includes('/products/')) {
                    const text = a.innerText.replace(/\\n/g, ' ').trim();
                    if (text.length > 0) {
                        items.push({ url: a.href, text: text });
                    }
                }
            });
            return items;
        }''')
        
        browser.close()

    # Sometimes grids have duplicate links (e.g. image link and text link pointing to same product)
    # Deduplicate based on URL
    unique_products = {}
    for p in products:
        unique_products[p['url']] = p

    new_items = []
    
    for url, data in unique_products.items():
        if url not in known_urls:
            new_items.append(data)
            known_urls.add(url)

    if new_items:
        print(f"Found {len(new_items)} new listings!")
        for item in new_items:
            print(f"- {item['text']} ({item['url']})")
        send_email(new_items)
        
        # Save updated known URLs back to the file
        with open(JSON_FILE, "w") as f:
            json.dump(list(known_urls), f, indent=4)
    else:
        print("No new listings found.")

if __name__ == "__main__":
    main()
