import json
import xml.etree.ElementTree as ET
from datetime import datetime

# 수집할 피드 목록 (코드에 내장하여 안정성 확보)
DEFAULT_FEEDS = [
    {"name": "SEC Press", "url": "https://www.sec.gov/news/pressreleases.rss"},
    {"name": "Bloomberg Finance", "url": "https://www.bloomberg.com/feeds/bfinance/most-read.xml"},
    {"name": "Reuters Business", "url": "https://www.reutersagency.com/feed/?best-topics=business&post_type=best"}
]

async def fetch_url(url, method="GET", body=None, headers=None):
    import js
    options = {"method": method}
    if body: options["body"] = body
    if headers: options["headers"] = headers
    
    response = await js.fetch(url, js.Object.fromEntries(js.Map.new(options.items())))
    text = await response.text()
    return text, response.status

def parse_rss(xml_content):
    try:
        root = ET.fromstring(xml_content)
        items = []
        for item in root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry"):
            title_node = item.find("title") or item.find("{http://www.w3.org/2005/Atom}title")
            link_node = item.find("link") or item.find("{http://www.w3.org/2005/Atom}link")
            desc_node = item.find("description") or item.find("{http://www.w3.org/2005/Atom}summary")
            
            title = title_node.text if title_node is not None else "No Title"
            link = ""
            if link_node is not None:
                link = link_node.get("href") if link_node.get("href") else link_node.text
            description = desc_node.text if desc_node is not None else ""
            
            items.append({'title': title, 'link': link or "", 'description': description, 'id': link or title})
        return items
    except: return []

async def on_scheduled(event, env, ctx):
    print(f"Cron triggered at {datetime.now()}")
    
    # Secrets 로드
    telegram_token = getattr(env, "TELEGRAM_TOKEN", None)
    telegram_chat_id = getattr(env, "TELEGRAM_CHAT_ID", None)
    gemini_key = getattr(env, "GEMINI_API_KEY", None)

    if not telegram_token or not gemini_key:
        print("Missing API keys in Environment Variables!")
        return

    for feed in DEFAULT_FEEDS:
        try:
            print(f"Checking: {feed['name']}")
            xml_text, status = await fetch_url(feed['url'])
            if status != 200: continue
            
            items = parse_rss(xml_text)
            for entry in items[:3]:
                if await env.NEWS_KV.get(entry['id']): continue
                
                print(f"New Insight for: {entry['title']}")
                
                # Gemini API
                gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-lite-latest:generateContent?key={gemini_key}"
                prompt = f"금융 전문 기자로서 아래 뉴스를 분석하여 [요약], [기자적 분석], [취재 제언] 형식으로 작성하라.\n\n제목: {entry['title']}\n내용: {entry['description']}"
                payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]})
                
                res_text, res_status = await fetch_url(gemini_url, method="POST", body=payload, headers={"Content-Type": "application/json"})
                if res_status != 200: continue
                
                res_json = json.loads(res_text)
                insight = res_json['candidates'][0]['content']['parts'][0]['text'].replace("*", "")
                
                # Telegram
                msg = f"🔔 <b>{feed['name']}</b>\n\n{insight}\n\n<a href='{entry['link']}'>원문 보기</a>"
                t_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
                t_data = json.dumps({"chat_id": telegram_chat_id, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": False})
                await fetch_url(t_url, method="POST", body=t_data, headers={"Content-Type": "application/json"})
                
                # KV 저장
                await env.NEWS_KV.put(entry['id'], "true")
                
        except Exception as e:
            print(f"Error in {feed['name']}: {e}")

    print("Cron task finished.")
