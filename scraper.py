import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

URL = "https://www.cettire.com/de/pages/search?qTitle=golden%20goose%20sneakers&menu%5Bdepartment%5D=men&menu%5Bproduct_type%5D=Sneakers&from=home.search_box_direct_query&query=golden%20goose%20sneakers&refinementList%5Btags%5D%5B0%5D=Shoes&refinementList%5BSize%5D%5B0%5D=EU40&refinementList%5BSize%5D%5B1%5D=EU41&page=1"

EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER") or EMAIL_SENDER
JSON_FILE = "known_listings.json"


def send_email(subject, html_body):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("Email credentials not set.")
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
                    known = {u: {"url": u, "text": ""} for u in known}
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

        clicks = 0
        while True:
            btn = page.query_selector(
                'button:has-text("Mehr laden"), '
                'button:has-text("Load More")'
            )
            if not btn or not btn.is_visible():
                print(f"Done loading after {clicks} clicks.")
                break
            btn.scroll_into_view_if_needed()
            btn.click()
            clicks += 1
            print(f"Clicked Mehr laden ({clicks})...")
            page.wait_for_timeout(3000)

        page.wait_for_timeout(2000)

        print("Extracting products...")
        products = page.evaluate(
            """() => {
            const items = [];
            document.querySelectorAll('a').forEach(a => {
                if (a.href && a.href.includes('/products/')) {
                    const text = a.innerText.replace(/\\n/g, ' ').trim();
                    if (text.length > 0)
                        items.push({url: a.href, text: text});
                }
            });
            return items;
        }"""
        )

        browser.close()

    current = {}
    for prod in products:
        current[prod["url"]] = prod

    print(f"Total products: {len(current)}")

    new_items = [d for u, d in current.items() if u not in known]
    removed_items = [d for u, d in known.items() if u not in current]

    if new_items or removed_items:
        html = ""
        if new_items:
            print(f"{len(new_items)} NEW listings!")
            html += "<h2 style='color:green'>New Listings</h2><ul>"
            for i in new_items:
                html += f"<li><a href='{i['url']}'>{i['text']}</a></li>"
            html += "</ul>"
        if removed_items:
            print(f"{len(removed_items)} REMOVED listings!")
            html += "<h2 style='color:red'>Removed Listings</h2><ul>"
            for i in removed_items:
                html += f"<li><a href='{i['url']}'>{i['text']}</a></li>"
            html += "</ul>"
        parts = []
        if new_items:
            parts.append(f"{len(new_items)} new")
        if removed_items:
            parts.append(f"{len(removed_items)} removed")
        send_email(
            f"Cettire Alert: {', '.join(parts)} Golden Goose listing(s)",
            html,
        )
        with open(JSON_FILE, "w") as f:
            json.dump(current, f, indent=4)
    else:
        print("No changes detected.")


if __name__ == "__main__":
    main()
