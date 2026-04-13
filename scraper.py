import json
import os
import re
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.cettire.com/de/pages/search?qTitle=golden%20goose&menu%5Bdepartment%5D=men&menu%5Bproduct_type%5D=Sneakers&from=home.search_box_direct_query&query=golden%20goose&refinementList%5Btags%5D%5B0%5D=Shoes&refinementList%5BColor%5D=&refinementList%5Bvendor%5D=&"
URL_40 = BASE_URL + "refinementList%5BSize%5D%5B0%5D=US7&refinementList%5BSize%5D%5B1%5D=UK6&refinementList%5BSize%5D%5B2%5D=IT40&refinementList%5BSize%5D%5B3%5D=EU40&refinementList%5BSize%5D%5B4%5D=BR38&refinementList%5BSize%5D%5B5%5D=KR250&refinementList%5BSize%5D%5B6%5D=JP25&refinementList%5BSize%5D%5B7%5D=FR41&page=1"
URL_41 = BASE_URL + "refinementList%5BSize%5D%5B0%5D=US8&refinementList%5BSize%5D%5B1%5D=UK7&refinementList%5BSize%5D%5B2%5D=IT41&refinementList%5BSize%5D%5B3%5D=EU41&refinementList%5BSize%5D%5B4%5D=BR39&refinementList%5BSize%5D%5B5%5D=KR260&refinementList%5BSize%5D%5B6%5D=JP26&refinementList%5BSize%5D%5B7%5D=FR42&page=1"

# === 🎯 EXACT VIP TARGETS ===
FAVORITE_URLS = [
    "https://www.cettire.com/de/products/golden-goose-deluxe-brand-superstar-low-top-sneakers-959556024/cmVhY3Rpb24vcHJvZHVjdDpMRkZxa2trcUFnZWJFa3B4OQ%3D%3D",
    "https://www.cettire.com/de/products/golden-goose-deluxe-brand-super-star-lace-up-sneakers-960142659/cmVhY3Rpb24vcHJvZHVjdDp3R0RaYnp6QnNzRXAyQ25OdQ%3D%3D",
    "https://www.cettire.com/de/products/golden-goose-deluxe-brand-superstar-low-top-sneakers-922506155/cmVhY3Rpb24vcHJvZHVjdDpaRWc0aHM5UkpFZE5XRTdpOQ%3D%3D"
]

EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER") or EMAIL_SENDER
JSON_FILE = "known_listings.json"


def get_product_id(url):
    m = re.search(r'/products/([^/]+)', url)
    return m.group(1) if m else None

FAV_IDS = [get_product_id(u) for u in FAVORITE_URLS if get_product_id(u)]

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


def scrape_dataset(page, url):
    print(f"Navigating to dataset: {url[-20:]}...")
    page.goto(url, timeout=60000)
    page.wait_for_timeout(5000)

    try:
        cookie_btn = page.query_selector('text=/Alle akzeptieren|Accept All/i')
        if cookie_btn:
            cookie_btn.evaluate("el => el.click()")
            page.wait_for_timeout(2000)
            page.reload(timeout=60000)
            page.wait_for_timeout(6000)
    except Exception:
        pass

    last_count = 0
    checks = 0
    for i in range(50):
        page.evaluate("window.scrollBy(0, 1000)")
        page.wait_for_timeout(1000)
        try:
            for el in page.query_selector_all('text=/Mehr laden|Load More/i'):
                el.evaluate("el => el.click()")
                page.wait_for_timeout(1500)
                break
        except Exception:
            pass
            
        cnt = page.evaluate("document.querySelectorAll('a[href*=\"/products/\"]').length")
        if cnt == last_count and cnt > 0:
            checks += 1
            if checks >= 3:
                break
        else:
            checks = 0 
        last_count = cnt

    return page.evaluate(
        """() => {
        const items = [];
        document.querySelectorAll('a').forEach(a => {
            if (a.href && a.href.includes('/products/')) {
                const img = a.querySelector('img');
                items.push({url: a.href, text: a.innerText.replace(/\\n/g, ' ').trim(), img: img ? img.src : ""});
            }
        });
        return items;
    }"""
    )


def generate_item_html(item):
    name = re.sub(r"€[\d.,]+", "", item["text"]).strip()
    name = re.sub(r"\s+", " ", name).strip()
    
    img_html = f'<img src="{item["img"]}" style="width: 55px; height: 55px; border-radius: 4px; border: 1px solid #eee; object-fit: cover;">' if item.get("img") else ''
    
    p40 = item.get("price_40")
    p41 = item.get("price_41")
    
    p40_str = f"€{p40:,.0f}" if p40 else "N/A"
    p41_str = f"€{p41:,.0f}" if p41 else "N/A"

    savings_badge = ""
    if p40 and p41 and p40 != p41:
        diff = abs(p40 - p41)
        better_sz = 40 if p40 < p41 else 41
        savings_badge = f'<span style="background: #fdf2e9; color: #d35400; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; margin-left: 8px;">💡 Save €{diff:,.0f} in {better_sz}!</span>'

    drop_badge = ""
    if item.get("drop_40"):
        drop_badge += f'<span style="background: #e8f4fd; color: #007bff; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 6px;">40 dropped €{item["drop_40"]:,.0f}</span>'
    if item.get("drop_41"):
         drop_badge += f'<span style="background: #e8f4fd; color: #007bff; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 6px;">41 dropped €{item["drop_41"]:,.0f}</span>'

    html = f"""
    <div style="padding: 12px 0; border-bottom: 1px solid #eee; display: flex; align-items: center; gap: 12px;">
        {img_html}
        <div style="flex: 1;">
            <a href="{item['url']}" style="color: #1a1a2e; text-decoration: none; font-weight: bold; font-size: 13px; display: block; margin-bottom: 4px;">{name} {drop_badge}</a>
            <div style="font-size: 13px; color: #555; display: flex; align-items: center;">
                <span style="background: #eee; padding: 2px 6px; border-radius: 4px; margin-right: 6px;">40 ➔ <b>{p40_str}</b></span>
                <span style="background: #eee; padding: 2px 6px; border-radius: 4px;">41 ➔ <b>{p41_str}</b></span>
                {savings_badge}
            </div>
        </div>
    </div>
    """
    return html


def build_email_html(price_drops, new_targets, favs, ballstars, superstars, avg_price, last_avg):
    now = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; background: #f8f9fa; padding: 20px; border-radius: 12px;">
        <div style="background: linear-gradient(135deg, #1a1a2e, #16213e); color: white; padding: 24px; border-radius: 10px; margin-bottom: 16px;">
            <h1 style="margin: 0 0 4px 0; font-size: 20px;">👟 Golden Goose Alert</h1>
            <p style="margin: 0; opacity: 0.7; font-size: 13px;">Size 40/41 Updates Found</p>
            <p style="margin: 0; opacity: 0.7; font-size: 11px; margin-top: 4px;">{now}</p>
        </div>
    """

    trend_html = ""
    if last_avg > 0:
        diff = avg_price - last_avg
        pct = (diff / last_avg) * 100
        arrow = "▲" if diff > 0 else "▼" if diff < 0 else "–"
        color = "#cc3333" if diff > 0 else "#2d8f2d" if diff < 0 else "#666"
        trend_html = f"<span style='color:{color};font-weight:bold'>{arrow} {abs(pct):.1f}%</span> vs last check"

    html += f"""
        <div style="background: white; padding: 16px; border-radius: 8px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center;">
            <div style="font-size: 12px; color: #666; margin-bottom: 4px;">Global Market Average (sizes 40 & 41)</div>
            <div style="font-size: 28px; font-weight: bold; color: #1a1a2e;">€{avg_price:,.0f}</div>
            <div style="font-size: 12px; color: #666; margin-top: 4px;">{trend_html}</div>
        </div>
    """

    if price_drops:
        html += """<div style="background: white; padding: 16px; border-radius: 8px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 4px solid #007bff;">
            <h2 style="margin: 0 0 12px 0; font-size: 18px; color: #007bff;">⬇️ Priority Price Drops</h2>"""
        for item in price_drops:
            html += generate_item_html(item)
        html += "</div>"
        
    if favs:
        html += """<div style="background: white; padding: 16px; border-radius: 8px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 4px solid #f1c40f;">
            <h2 style="margin: 0 0 12px 0; font-size: 18px; color: #f39c12;">⭐ VIP Target Watchlist</h2>"""
        for item in favs:
            html += generate_item_html(item)
        html += "</div>"

    if new_targets:
        html += """<div style="background: white; padding: 16px; border-radius: 8px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 4px solid #8e44ad;">
            <h2 style="margin: 0 0 12px 0; font-size: 18px; color: #8e44ad;">✨ New Priority Models</h2>"""
        for item in new_targets:
            html += generate_item_html(item)
        html += "</div>"

    if ballstars:
        html += """<div style="background: white; padding: 16px; border-radius: 8px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 4px solid #2d8f2d;">
            <h2 style="margin: 0 0 12px 0; font-size: 18px; color: #2d8f2d;">🟢 Top 5 Market Ball Stars (Valid in 40)</h2>"""
        for item in ballstars:
            html += generate_item_html(item)
        html += "</div>"

    if superstars:
        html += """<div style="background: white; padding: 16px; border-radius: 8px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 4px solid #f39c12;">
            <h2 style="margin: 0 0 12px 0; font-size: 18px; color: #d35400;">🔥 Top 5 Market Super-Stars (Valid in 41)</h2>"""
        for item in superstars:
            html += generate_item_html(item)
        html += "</div>"
        
    html += "</div></div>"
    return html


def send_email(subject, html_body):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
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
    except Exception as e:
        print(e)


def main():
    known = {}
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r") as f:
                known = json.load(f)
        except Exception:
            pass

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page.set_viewport_size({"width": 1920, "height": 1080})

        raw_40 = scrape_dataset(page, URL_40)
        raw_41 = scrape_dataset(page, URL_41)
        browser.close()

    current = {}
    
    # Process Size 40
    for item in raw_40:
        if not item["text"]: continue
        url = item["url"]
        if url not in current:
            current[url] = {"url": url, "text": item["text"], "img": item["img"], "price_40": None, "price_41": None}
        current[url]["price_40"] = parse_price(item["text"])
        
    # Process Size 41
    for item in raw_41:
        if not item["text"]: continue
        url = item["url"]
        if url not in current:
            current[url] = {"url": url, "text": item["text"], "img": item["img"], "price_40": None, "price_41": None}
        current[url]["text"] = item["text"]
        if not current[url]["img"]:
             current[url]["img"] = item["img"]
        current[url]["price_41"] = parse_price(item["text"])

    # Map global averages before slicing
    current_prices = [val for doc in current.values() for key, val in doc.items() if key in ("price_40", "price_41") and val]
    avg_price = sum(current_prices) / len(current_prices) if current_prices else 0
    
    known_prices = [val for doc in known.values() for key, val in doc.items() if key in ("price_40", "price_41") and val if not isinstance(val, list)]
    last_avg = sum(known_prices) / len(known_prices) if known_prices else 0

    # Detect Price Drops & State Syncing
    price_drops = []
    
    # 🎯 Historical Tracking Reinstatement 
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    
    for u, doc in current.items():
        if u in known:
            k_40 = known[u].get("price_40")
            k_41 = known[u].get("price_41")
            
            c_40 = doc["price_40"]
            c_41 = doc["price_41"]
            
            drop_40 = (k_40 - c_40) if (k_40 and c_40 and c_40 < k_40) else 0
            drop_41 = (k_41 - c_41) if (k_41 and c_41 and c_41 < k_41) else 0
            
            if drop_40 > 0 or drop_41 > 0:
                name = doc["text"].lower()
                if 'ball' in name or 'super' in name:
                    drop_item = dict(doc)
                    drop_item["drop_40"] = drop_40
                    drop_item["drop_41"] = drop_41
                    price_drops.append(drop_item)

        # Restore History Accumulation logic to the JSON
        doc["history_40"] = known.get(u, {}).get("history_40", [])
        doc["history_41"] = known.get(u, {}).get("history_41", [])
        
        last_hist_40 = doc["history_40"][-1]["price"] if doc["history_40"] else None
        last_hist_41 = doc["history_41"][-1]["price"] if doc["history_41"] else None
        
        if doc["price_40"] and doc["price_40"] != last_hist_40:
            doc["history_40"].append({"date": now_str, "price": doc["price_40"]})
        
        if doc["price_41"] and doc["price_41"] != last_hist_41:
            doc["history_41"].append({"date": now_str, "price": doc["price_41"]})


    # Detect completely new target inventory
    new_targets = []
    for u, doc in current.items():
        if u not in known:
            name = doc["text"].lower()
            if ('ball' in name and doc["price_40"] is not None) or ('super' in name and doc["price_41"] is not None):
                new_targets.append(doc)
                
    # 🎯 Match exact Favorite URLs
    favs = []
    for u, doc in current.items():
        if get_product_id(u) in FAV_IDS:
            favs.append(doc)

    # Filter & Sort strictly Ball Stars (Size 40 Required)
    ballstars = [d for d in current.values() if 'ball' in d["text"].lower() and d["price_40"] is not None]
    ballstars = sorted(ballstars, key=lambda x: x["price_40"])[:5]

    # Filter & Sort strictly Super-Stars (Size 41 Required)
    superstars = [d for d in current.values() if 'super' in d["text"].lower() and d["price_41"] is not None]
    superstars = sorted(superstars, key=lambda x: x["price_41"])[:5]

    # MASTER TRIGGER: Run if anything changed OR if VIP target is alive
    if price_drops or new_targets or favs:
        html = build_email_html(price_drops, new_targets, favs, ballstars, superstars, avg_price, last_avg)
        
        subject_parts = []
        if price_drops: subject_parts.append(f"{len(price_drops)} Drops")
        if favs: subject_parts.append(f"⭐ VIP Found")
        if new_targets: subject_parts.append(f"{len(new_targets)} New")
        
        subject = f"Cettire Deal Alert: {', '.join(subject_parts)}" if subject_parts else "Cettire Deal Alert"
        send_email(subject, html)
        print("Alert email sent.")
    else:
        print("No new updates. Email skipped.")

    # Always save state persistence even if no email was sent
    with open(JSON_FILE, "w") as f:
        json.dump(current, f, indent=4)

if __name__ == "__main__":
    main()
