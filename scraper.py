import json
import os
import re
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

# Using your URL that loads everything up to page 2
URL = "https://www.cettire.com/de/pages/search?qTitle=golden%20goose%20sneakers&menu%5Bdepartment%5D=men&menu%5Bproduct_type%5D=Sneakers&from=home.search_box_direct_query&query=golden%20goose%20sneakers&refinementList%5Btags%5D%5B0%5D=Shoes&refinementList%5BSize%5D%5B0%5D=EU40&refinementList%5BSize%5D%5B1%5D=EU41&page=2"

EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER") or EMAIL_SENDER
JSON_FILE = "known_listings.json"


def parse_price(text):
    prices = re.findall(r"€([\d.,]+)", text)
    parsed = []
    for p in prices:
        try:
            cleaned = p.replace(".", "").replace(",", ".")
            parsed.append(float(cleaned))
        except ValueError:
            pass
    return min(parsed) if parsed else None


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


def build_email_html(current, new_items, removed_items, price_history):
    now = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    prices = [p for p in (parse_price(d["text"]) for d in current.values()) if p]
    avg_price = sum(prices) / len(prices) if prices else 0
    min_price = min(prices) if prices else 0
    max_price = max(prices) if prices else 0

    trend_html = ""
    if len(price_history) >= 2:
        prev_avg = price_history[-2]["avg_price"]
        diff = avg_price - prev_avg
        pct = (diff / prev_avg) * 100 if prev_avg else 0
        arrow = "▲" if diff > 0 else "▼" if diff < 0 else "–"
        color = "#cc3333" if diff > 0 else "#2d8f2d" if diff < 0 else "#666"
        trend_html = f"<span style='color:{color};font-weight:bold'>{arrow} {abs(pct):.1f}%</span> vs last check"

    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; background: #f8f9fa; padding: 20px; border-radius: 12px;">
        <div style="background: linear-gradient(135deg, #1a1a2e, #16213e); color: white; padding: 24px; border-radius: 10px; margin-bottom: 16px;">
            <h1 style="margin: 0 0 4px 0; font-size: 20px;">👟 Golden Goose Tracker</h1>
            <p style="margin: 0; opacity: 0.7; font-size: 12px;">{now}</p>
        </div>

        <div style="display: flex; gap: 10px; margin-bottom: 16px;">
            <div style="flex: 1; background: white; padding: 16px; border-radius: 8px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                <div style="font-size: 28px; font-weight: bold; color: #1a1a2e;">{len(current)}</div>
                <div style="font-size: 12px; color: #666;">Total Listings</div>
            </div>
            <div style="flex: 1; background: white; padding: 16px; border-radius: 8px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                <div style="font-size: 28px; font-weight: bold; color: #1a1a2e;">€{avg_price:,.0f}</div>
                <div style="font-size: 12px; color: #666;">Avg Price {trend_html}</div>
            </div>
            <div style="flex: 1; background: white; padding: 16px; border-radius: 8px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                <div style="font-size: 28px; font-weight: bold; color: #2d8f2d;">€{min_price:,.0f}</div>
                <div style="font-size: 12px; color: #666;">Cheapest</div>
            </div>
        </div>
    """

    if new_items:
        html += """<div style="background: white; padding: 16px; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <h2 style="margin: 0 0 12px 0; font-size: 16px; color: #2d8f2d;">🟢 New Listings</h2>"""
        for i in new_items:
            price = parse_price(i["text"])
            price_str = f"€{price:,.2f}" if price else "N/A"
            name = re.sub(r"€[\d.,]+", "", i["text"]).strip()
            name = re.sub(r"\s+", " ", name).strip()
            html += f"""<div style="padding: 10px 0; border-bottom: 1px solid #eee;">
                <a href="{i['url']}" style="color: #1a1a2e; text-decoration: none; font-weight: 500;">{name}</a>
                <span style="float: right; color: #2d8f2d; font-weight: bold;">{price_str}</span>
            </div>"""
        html += "</div>"

    if removed_items:
        html += """<div style="background: white; padding: 16px; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <h2 style="margin: 0 0 12px 0; font-size: 16px; color: #cc3333;">🔴 Removed Listings</h2>"""
        for i in removed_items:
            price = parse_price(i["text"])
            price_str = f"€{price:,.2f}" if price else "N/A"
            name = re.sub(r"€[\d.,]+", "", i["text"]).strip()
            name = re.sub(r"\s+", " ", name).strip()
            html += f"""<div style="padding: 10px 0; border-bottom: 1px solid #eee;">
                <a href="{i['url']}" style="color: #999; text-decoration: line-through;">{name}</a>
                <span style="float: right; color: #cc3333;">{price_str}</span>
            </div>"""
        html += "</div>"

    if len(price_history) > 1:
        html += """<div style="background: white; padding: 16px; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <h2 style="margin: 0 0 12px 0; font-size: 16px; color: #1a1a2e;">📈 Price History</h2>
            <table style="width: 100%; font-size: 13px; border-collapse: collapse;">
            <tr style="color: #666;"><th style="text-align:left;padding:4px;">Date</th><th style="text-align:right;padding:4px;">Avg Price</th><th style="text-align:right;padding:4px;">Listings</th></tr>"""
        for entry in price_history[-10:]:
            html += f"""<tr><td style="padding:4px;">{entry['date']}</td>
                <td style="text-align:right;padding:4px;">€{entry['avg_price']:,.2f}</td>
                <td style="text-align:right;padding:4px;">{entry['count']}</td></tr>"""
        html += "</table></div>"

    html += "</div>"
    return html


def main():
    data = {"listings": {}, "price_history": []}
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict) and "listings" in loaded:
                    data = loaded
                elif isinstance(loaded, dict):
                    data["listings"] = loaded
                elif isinstance(loaded, list):
                    data["listings"] = {u: {"url": u, "text": ""} for u in loaded}
        except Exception:
            pass

    known = data["listings"]
    price_history = data.get("price_history", [])

    print("Launching browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        print("Navigating to Cettire...")
        page.goto(URL, timeout=60000)
        page.wait_for_timeout(8000)

        print("Scrolling page to load all items...")
        last_height = page.evaluate("document.body.scrollHeight")
        while True:
            # Scroll to the absolute bottom of the page
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(3000) # Wait for network load
            
            # Click any load more buttons if they unexpectedly appear
            try:
                load_btn = page.query_selector('text="Mehr laden"') or page.query_selector('text="Load More"')
                if load_btn and load_btn.is_visible():
                    load_btn.click()
                    page.wait_for_timeout(2000)
            except Exception:
                pass
                
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                # Give it one more final scroll check just in case
                page.wait_for_timeout(2000)
                if page.evaluate("document.body.scrollHeight") == last_height:
                    break
            last_height = new_height

        print("Extracting products...")
        products = page.evaluate(
            """() => {
            const items = [];
            // Finds all links that have /products/ in the URL
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

    print(f"Total products found: {len(current)}")

    new_items = [d for u, d in current.items() if u not in known]
    removed_items = [d for u, d in known.items() if u not in current]

    prices = [p for p in (parse_price(d["text"]) for d in current.values()) if p]
    avg_price = sum(prices) / len(prices) if prices else 0
    now = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M")
    
    # Only append to history if prices exist so we don't skew data
    if current:
        price_history.append({"date": now, "avg_price": round(avg_price, 2), "count": len(current)})

    # ALWAYS send email for now
    if True:
        print(f"{len(new_items)} NEW, {len(removed_items)} REMOVED")
        html = build_email_html(current, new_items, removed_items, price_history)
        parts = []
        if new_items:
            parts.append(f"{len(new_items)} new")
        if removed_items:
            parts.append(f"{len(removed_items)} removed")
        subject = f"Cettire Alert: {', '.join(parts)} Golden Goose listing(s)" if parts else "Cettire Report: Golden Goose Tracker Update"
        send_email(subject, html)

    data["listings"] = current
    data["price_history"] = price_history
    with open(JSON_FILE, "w") as f:
        json.dump(data, f, indent=4)


if __name__ == "__main__":
    main()
