import json
import os
import re
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

URL = "https://www.cettire.com/de/pages/search?qTitle=golden%20goose%20sneakers&menu%5Bdepartment%5D=men&menu%5Bproduct_type%5D=Sneakers&from=home.search_box_direct_query&query=golden%20goose%20sneakers"

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


def is_target_model(text):
    # Case insensitive match for 'ball star', 'ballstar', 'super star', or 'superstar'
    return bool(re.search(r'\b(ball\s*star|super\s*star)\b', text, re.IGNORECASE))


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


def build_email_html(current, new_targets, price_drops, removed_items, price_history):
    now = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    
    # Calculate overall dashboard stats
    prices = [d["price"] for d in current.values() if d.get("price")]
    avg_price = sum(prices) / len(prices) if prices else 0
    min_price = min(prices) if prices else 0

    trend_html = ""
    if len(price_history) >= 2:
        prev_avg = price_history[-2]["avg_price"]
        diff = avg_price - prev_avg
        pct = (diff / prev_avg) * 100 if prev_avg else 0
        arrow = "▲" if diff > 0 else "▼" if diff < 0 else "–"
        color = "#cc3333" if diff > 0 else "#2d8f2d" if diff < 0 else "#666"
        trend_html = f"<span style='color:{color};font-weight:bold'>{arrow} {abs(pct):.1f}%</span> vs last check"

    # Start HTML layout
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; background: #f8f9fa; padding: 20px; border-radius: 12px;">
        <div style="background: linear-gradient(135deg, #1a1a2e, #16213e); color: white; padding: 24px; border-radius: 10px; margin-bottom: 16px;">
            <h1 style="margin: 0 0 4px 0; font-size: 20px;">👟 Golden Goose Tracker</h1>
            <p style="margin: 0; opacity: 0.7; font-size: 12px;">{now}</p>
        </div>
    """

    if new_targets:
        html += """<div style="background: white; padding: 16px; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 4px solid #2d8f2d;">
            <h2 style="margin: 0 0 12px 0; font-size: 18px; color: #2d8f2d;">🟢 New Target Models (Ball/Super)</h2>"""
        for i in new_targets:
            price_str = f"€{i['price']:,.2f}" if i.get('price') else "N/A"
            name = re.sub(r"€[\d.,]+", "", i["text"]).strip()
            name = re.sub(r"\s+", " ", name).strip()
            html += f"""<div style="padding: 10px 0; border-bottom: 1px solid #eee;">
                <a href="{i['url']}" style="color: #1a1a2e; text-decoration: none; font-weight: 500;">{name}</a>
                <span style="float: right; color: #2d8f2d; font-weight: bold; font-size: 15px;">{price_str}</span>
            </div>"""
        html += "</div>"

    if price_drops:
        html += """<div style="background: white; padding: 16px; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 4px solid #007bff;">
            <h2 style="margin: 0 0 12px 0; font-size: 18px; color: #007bff;">⬇️ Price Drops</h2>"""
        for item in price_drops:
            name = re.sub(r"€[\d.,]+", "", item["text"]).strip()
            name = re.sub(r"\s+", " ", name).strip()
            html += f"""<div style="padding: 10px 0; border-bottom: 1px solid #eee;">
                <a href="{item['url']}" style="color: #1a1a2e; text-decoration: none; font-weight: 500;">{name}</a>
                <div style="float: right;">
                    <span style="color: #999; text-decoration: line-through; margin-right: 8px;">€{item['old_price']:,.2f}</span>
                    <span style="color: #2d8f2d; font-weight: bold; font-size: 15px;">€{item['new_price']:,.2f}</span>
                </div>
            </div>"""
        html += "</div>"

    # Dashboard has been re-ordered to the middle
    html += f"""
        <h2 style="font-size: 16px; color: #1a1a2e; margin: 20px 0 10px 0; padding-left: 4px;">Market Overview (All Categories)</h2>
        <div style="display: flex; gap: 10px; margin-bottom: 16px;">
            <div style="flex: 1; background: white; padding: 16px; border-radius: 8px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                <div style="font-size: 28px; font-weight: bold; color: #1a1a2e;">{len(current)}</div>
                <div style="font-size: 12px; color: #666;">Total Listings</div>
            </div>
            <div style="flex: 1; background: white; padding: 16px; border-radius: 8px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                <div style="font-size: 28px; font-weight: bold; color: #1a1a2e;">€{avg_price:,.0f}</div>
                <div style="font-size: 12px; color: #666;">Avg Price <br>{trend_html}</div>
            </div>
            <div style="flex: 1; background: white; padding: 16px; border-radius: 8px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                <div style="font-size: 28px; font-weight: bold; color: #2d8f2d;">€{min_price:,.0f}</div>
                <div style="font-size: 12px; color: #666;">Cheapest</div>
            </div>
        </div>
    """

    if removed_items:
        html += """<div style="background: white; padding: 16px; border-radius: 8px; margin-bottom: 12px; opacity: 0.8;">
            <h2 style="margin: 0 0 12px 0; font-size: 14px; color: #cc3333;">🔴 Removed / Sold Out</h2>"""
        for i in removed_items:
            price_str = f"€{i['price']:,.2f}" if i.get('price') else "N/A"
            name = re.sub(r"€[\d.,]+", "", i["text"]).strip()
            name = re.sub(r"\s+", " ", name).strip()
            html += f"""<div style="padding: 6px 0; border-bottom: 1px solid #eee; font-size: 13px;">
                <span style="color: #999; text-decoration: line-through;">{name}</span>
                <span style="float: right; color: #cc3333;">{price_str}</span>
            </div>"""
        html += "</div>"

    if len(price_history) > 1:
        html += """<div style="background: white; padding: 16px; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <h2 style="margin: 0 0 12px 0; font-size: 14px; color: #1a1a2e;">📈 Price History</h2>
            <table style="width: 100%; font-size: 12px; border-collapse: collapse;">
            <tr style="color: #666;"><th style="text-align:left;padding:4px;border-bottom:1px solid #eee;">Date</th><th style="text-align:right;padding:4px;border-bottom:1px solid #eee;">Avg Price</th><th style="text-align:right;padding:4px;border-bottom:1px solid #eee;">Listings</th></tr>"""
        for entry in price_history[-10:]:
            html += f"""<tr><td style="padding:4px;">{entry['date']}</td>
                <td style="text-align:right;padding:4px;">€{entry['avg_price']:,.2f}</td>
                <td style="text-align:right;padding:4px;">{entry['count']}</td></tr>"""
        html += "</table></div>"

    html += "</div>"
    return html


def count_products(page):
    return page.evaluate("""() => {
        let count = 0;
        document.querySelectorAll('a').forEach(a => {
            if (a.href && a.href.includes('/products/')) count++;
        });
        return count;
    }""")


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
    # Automatically upgrade old database entries on the fly safely
    for k, v in known.items():
        if "price" not in v and "text" in v:
            v["price"] = parse_price(v["text"])

    price_history = data.get("price_history", [])

    print("Launching browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page.set_viewport_size({"width": 1920, "height": 1080})

        print("Navigating to Cettire...")
        page.goto(URL, timeout=60000)
        page.wait_for_timeout(5000)

        print("Looking for cookie banner...")
        try:
            cookie_btn = page.query_selector('text=/Alle akzeptieren|Accept All/i')
            if cookie_btn:
                cookie_btn.evaluate("el => el.click()")
                page.wait_for_timeout(2000)
                page.reload(timeout=60000)
                page.wait_for_timeout(6000)
        except Exception as e:
            print(f"Failed to click cookies: {e}")

        last_product_count = 0
        unchanged_checks = 0
        max_loops = 100 
        
        for i in range(max_loops):
            page.evaluate("window.scrollBy(0, 1000)")
            page.wait_for_timeout(1500)
            
            try:
                load_more_elements = page.query_selector_all('text=/Mehr laden|Load More/i')
                for el in load_more_elements:
                    el.evaluate("el => el.click()")
                    page.wait_for_timeout(2500)
                    break
            except Exception:
                pass
                
            current_count = count_products(page)
            print(f"Extraction Pass {i+1}: Found {current_count} products so far...")
            
            if current_count == last_product_count and current_count > 0:
                unchanged_checks += 1
                if unchanged_checks >= 3:
                    print("Hit the solid bottom of the list!")
                    break
            else:
                unchanged_checks = 0 
                
            last_product_count = current_count

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
        prod["price"] = parse_price(prod["text"])
        current[prod["url"]] = prod

    # Identify individual Price Drops
    price_drops = []
    for u, cur_doc in current.items():
        if u in known:
            old_price = known[u].get("price")
            new_price = cur_doc.get("price")
            if old_price and new_price and new_price < old_price:
                price_drops.append({
                    "url": u,
                    "text": cur_doc["text"],
                    "old_price": old_price,
                    "new_price": new_price
                })

    new_items = [d for u, d in current.items() if u not in known]
    removed_items = [d for u, d in known.items() if u not in current]
    
    # Filter the New Items section exclusively for Ball Star and Super-Star
    new_targets = [i for i in new_items if is_target_model(i["text"])]

    prices = [d["price"] for d in current.values() if d.get("price")]
    avg_price = sum(prices) / len(prices) if prices else 0
    now = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M")
    
    if current:
        price_history.append({"date": now, "avg_price": round(avg_price, 2), "count": len(current)})

    if True: # Always sending email right now for testing
        print(f"{len(new_items)} NEW (all types), {len(new_targets)} NEW TARGETS, {len(price_drops)} PRICE DROPS")
        html = build_email_html(current, new_targets, price_drops, removed_items, price_history)
        
        parts = []
        if new_targets:
            parts.append(f"{len(new_targets)} new target(s)")
        if price_drops:
            parts.append(f"{len(price_drops)} price drop(s)")
            
        subject = f"Cettire Alert: {', '.join(parts)}" if parts else "Cettire Report: Tracker Update"
        send_email(subject, html)

    data["listings"] = current
    data["price_history"] = price_history
    with open(JSON_FILE, "w") as f:
        json.dump(data, f, indent=4)

if __name__ == "__main__":
    main()
