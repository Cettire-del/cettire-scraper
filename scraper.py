import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

URL = "https://www.cettire.com/de/pages/search?qTitle=golden%20goose%20sneakers&menu%5Bdepartment%5D=men&menu%5Bproduct_type%5D=Sneakers&from=home.search_box_direct_query&query=golden%20goose%20sneakers&refinementList%5Btags%5D%5B0%5D=Shoes&refinementList%5BColor%5D=&refinementList%5Bvendor%5D=&refinementList%5BSize%5D%5B0%5D=US7&refinementList%5BSize%5D%5B1%5D=UK6&refinementList%5BSize%5D%5B2%5D=IT40&refinementList%5BSize%5D%5B3%5D=EU40&refinementList%5BSize%5D%5B4%5D=BR38&refinementList%5BSize%5D%5B5%5D=KR250&refinementList%5BSize%5D%5B6%5D=JP25&refinementList%5BSize%5D%5B7%5D=FR41&refinementList%5BSize%5D%5B8%5D=US8&refinementList%5BSize%5D%5B9%5D=UK7&refinementList%5BSize%5D%5B10%5D=IT41&refinementList%5BSize%5D%5B11%5D=EU41&refinementList%5BSize%5D%5B12%5D=BR39&refinementList%5BSize%5D%5B13%5D=KR260&refinementList%5BSize%5D%5B14%5D=JP26&refinementList%5BSize%5D%5B15%5D=FR42&page=1"

EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER") or EMAIL_SENDER

JSON_FILE = "known_listings.json"


def send_email(subject, html_body):
        if not EMAIL_SENDER or not EMAIL_PASSWORD:
                    print("Email credentials not set. Skipping email.")
                    return

        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECEIVER
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))

    try:
                server = smtplib.SMTP("smtp.gmail.com", 587)
                server.starttls()
                server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                server.send_message(msg)
                server.quit()
                print("Email sent successfully!")
except Exception as e:
            print(f"Failed to send email: {e}")


def main():
        known = {}
        if os.path.exists(JSON_FILE):
                    try:
                                    with open(JSON_FILE, "r") as f:
                                                        known = json.load(f)
                                                        if isinstance(known, list):
                                                                                known = {url: {"url": url, "text": ""} for url in known}
                    except Exception:
                                    pass

                print("Launching browser...")
    with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )

        print("Navigating to Cettire...")
        page.goto(URL, timeout=60000)
        page.wait_for_timeout(8000)

        load_more_clicks = 0
        while True:
                        btn = page.query_selector('button:has-text("Mehr laden"), button:has-text("Load More"), button:has-text("mehr laden")')
                        if not btn or not btn.is_visible():
                                            print(f"No more Load More button after {load_more_clicks} clicks.")
                                            break
                                        btn.scroll_into_view_if_needed()
            btn.click()
            load_more_clicks += 1
            print(f"Clicked Mehr laden ({load_more_clicks})...")
            page.wait_for_timeout(3000)

        page.wait_for_timeout(2000)

        print("Extracting products...")
        products = page.evaluate(
                        """() => {
                                    const items = [];
                                                document.querySelectorAll('a').forEach(a => {
                                                                if (a.href && a.href.includes('/products/')) {
                                                                                    const text = a.innerText.replace(/\\n/g, ' ').trim();
                                                                                                        if (text.length > 0) {
                                                                                                                                items.push({ url: a.href, text: text });
                                                                                                                                                    }
                                                                                                                                                                    }
                                                                                                                                                                                });
                                                                                                                                                                                            return items;
                                                                                                                                                                                                    }"""
        )

        browser.close()

    current = {}
    for prod in products:
                current[prod["url"]] = prod

    print(f"Total unique products found: {len(current)}")

    new_items = []
    removed_items = []

    for url, data in current.items():
                if url not in known:
                                new_items.append(data)

    for url, data in known.items():
                if url not in current:
                                removed_items.append(data)

    if new_items or removed_items:
                html_body = ""

        if new_items:
                        print(f"Found {len(new_items)} NEW listings!")
            for item in new_items:
                                print(f"  + {item['text']} ({item['url']})")
                            html_body += "<h2 style='color: #2d8f2d;'>New Listings</h2><ul>"
            for item in new_items:
                                html_body += f"<li><a href='{item['url']}'><b>{item['text']}</b></a></li>"
                            html_body += "</ul>"

        if removed_items:
                        print(f"Found {len(removed_items)} REMOVED listings!")
            for item in removed_items:
                                print(f"  - {item['text']} ({item['url']})")
                            html_body += "<h2 style='color: #cc3333;'>Removed Listings</h2><ul>"
            for item in removed_items:
                                html_body += f"<li><a href='{item['url']}'><b>{item['text']}</b></a></li>"
                            html_body += "</ul>"

        subject_parts = []
        if new_items:
                        subject_parts.append(f"{len(new_items)} new")
        if removed_items:
                        subject_parts.append(f"{len(removed_items)} removed")
        subject = f"Cettire Alert: {', '.join(subject_parts)} Golden Goose listing(s)"

        send_email(subject, html_body)

        with open(JSON_FILE, "w") as f:
                        json.dump(current, f, indent=4)
else:
        print("No changes detected.")


if __name__ == "__main__":
        main()
