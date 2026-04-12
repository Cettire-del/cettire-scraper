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

EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER") or EMAIL_SENDER


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


def build_email_html(top_10):
    now = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; background: #f8f9fa; padding: 20px; border-radius: 12px;">
        <div style="background: linear-gradient(135deg, #1a1a2e, #16213e); color: white; padding: 24px; border-radius: 10px; margin-bottom: 16px;">
            <h1 style="margin: 0 0 4px 0; font-size: 20px;">👟 Top 10 Priority Golden Goose</h1>
            <p style="margin: 0; opacity: 0.7; font-size: 13px;">Superstars (Size 41) & Ballstars (Size 40)</p>
            <p style="margin: 0; opacity: 0.7; font-size: 11px; margin-top: 4px;">{now}</p>
        </div>
        
        <div style="background: white; padding: 16px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 4px solid #f39c12;">
            <h2 style="margin: 0 0 12px 0; font-size: 18px; color: #d35400;">🔥 Absolute Best Deals</h2>
    """

    for item in top_10:
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

        html += f"""
        <div style="padding: 12px 0; border-bottom: 1px solid #eee; display: flex; align-items: center; gap: 12px;">
            {img_html}
            <div style="flex: 1;">
                <a href="{item['url']}" style="color: #1a1a2e; text-decoration: none; font-weight: bold; font-size: 13px; display: block; margin-bottom: 4px;">{name}</a>
                <div style="font-size: 13px; color: #555; display: flex; align-items: center;">
                    <span style="background: #eee; padding: 2px 6px; border-radius: 4px; margin-right: 6px;">40 ➔ <b>{p40_str}</b></span>
                    <span style="background: #eee; padding: 2px 6px; border-radius: 4px;">41 ➔ <b>{p41_str}</b></span>
                    {savings_badge}
                </div>
            </div>
        </div>
        """

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
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page.set_viewport_size({"width": 1920, "height": 1080})

        raw_40 = scrape_dataset(page, URL_40)
        raw_41 = scrape_dataset(page, URL_41)
        browser.close()

    combined = {}
    
    # Process Size 40
    for item in raw_40:
        if not item["text"]: continue
        url = item["url"]
        if url not in combined:
            combined[url] = {"url": url, "text": item["text"], "img": item["img"], "price_40": None, "price_41": None}
        combined[url]["price_40"] = parse_price(item["text"])
        
    # Process Size 41
    for item in raw_41:
        if not item["text"]: continue
        url = item["url"]
        if url not in combined:
            combined[url] = {"url": url, "text": item["text"], "img": item["img"], "price_40": None, "price_41": None}
        combined[url]["text"] = item["text"]
        if not combined[url]["img"]:
             combined[url]["img"] = item["img"]
        combined[url]["price_41"] = parse_price(item["text"])

    # Sorting Engine
    def sort_logic(doc):
        name = doc["text"].lower()
        is_ball_40 = 'ball' in name and doc["price_40"] is not None
        is_super_41 = 'super' in name and doc["price_41"] is not None
        
        is_priority = is_ball_40 or is_super_41
        
        # Determine absolute cheapest price it possesses across the two sizes
        min_p = min([p for p in (doc["price_40"], doc["price_41"]) if p] or [999999])
        
        # Sort so that Priority Items (True) come entirely before Non-Priority Items (False)
        return (not is_priority, min_p)

    sorted_shoes = sorted(list(combined.values()), key=sort_logic)
    top_10 = sorted_shoes[:10]
    
    if top_10:
        html = build_email_html(top_10)
        send_email("Cettire Sneaker Deals: Top 10 Priority Picks", html)
        print("Completed successfully.")

if __name__ == "__main__":
    main()
