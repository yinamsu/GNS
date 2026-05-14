import json
import xml.etree.ElementTree as ET
from datetime import datetime

DEFAULT_FEEDS = [
    {"name": "SEC Press", "url": "https://www.sec.gov/news/pressreleases.rss"},
    {"name": "Bloomberg Finance", "url": "https://www.bloomberg.com/feeds/bfinance/most-read.xml"},
    {"name": "Reuters Business", "url": "https://www.reutersagency.com/feed/?best-topics=business&post_type=best"}
]

async def log_to_kv(env, message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    full_log = f"[{timestamp}] {message}"
    print(full_log)
    try:
        logs = await env.NEWS_KV.get("SYSTEM_LOGS")
        logs_list = json.loads(logs) if logs else []
        logs_list.insert(0, full_log)
        await env.NEWS_KV.put("SYSTEM_LOGS", json.dumps(logs_list[:30]))
    except: pass

async def fetch_url(url, method="GET", body=None, headers=None):
    import js
    # Python dict를 JS object로 변환하는 가장 안전한 방법
    options = {"method": method}
    if body: options["body"] = body
    if headers: options["headers"] = headers
    
    js_options = js.JSON.parse(json.dumps(options))
    response = await js.fetch(url, js_options)
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
            items.append({'title': title, 'link': link or "", 'description': desc_node.text if desc_node is not None else "", 'id': link or title})
        return items
    except: return []

async def on_fetch(request, env, ctx):
    import js
    if request.method == "POST":
        try:
            body = await request.json()
            await log_to_kv(env, "Telegram signal received!")
            
            if "message" in body and "text" in body["message"]:
                text = body["message"]["text"]
                chat_id = body["message"]["chat"]["id"]
                
                if text == "/logs" or text == "/start":
                    await log_to_kv(env, f"Processing command: {text}")
                    logs = await env.NEWS_KV.get("SYSTEM_LOGS")
                    logs_list = json.loads(logs) if logs else ["No logs."]
                    response_text = "📋 <b>GNS Status Log</b>\n\n" + "\n".join(logs_list)
                    
                    token = getattr(env, "TELEGRAM_TOKEN", "")
                    t_url = f"https://api.telegram.org/bot{token}/sendMessage"
                    t_data = json.dumps({"chat_id": chat_id, "text": response_text, "parse_mode": "HTML"})
                    await fetch_url(t_url, method="POST", body=t_data, headers={"Content-Type": "application/json"})
                    
            return js.Response.new("OK")
        except Exception as e:
            await log_to_kv(env, f"Fetch Error: {str(e)}")
            return js.Response.new("Error")
    
    return js.Response.new("GNS Worker is Running")

async def on_scheduled(event, env, ctx):
    await log_to_kv(env, "Starting News Crawl...")
    token = getattr(env, "TELEGRAM_TOKEN", None)
    chat_id = getattr(env, "TELEGRAM_CHAT_ID", None)
    gemini_key = getattr(env, "GEMINI_API_KEY", None)

    for feed in DEFAULT_FEEDS:
        try:
            xml_text, status = await fetch_url(feed['url'])
            if status != 200: continue
            
            items = parse_rss(xml_text)
            for entry in items[:2]:
                if await env.NEWS_KV.get(entry['id']): continue
                
                # Gemini REST
                gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-lite-latest:generateContent?key={gemini_key}"
                payload = json.dumps({"contents": [{"parts": [{"text": f"분석하라: {entry['title']}\n{entry['description']}"}]}]})
                res_text, res_status = await fetch_url(gemini_url, method="POST", body=payload, headers={"Content-Type": "application/json"})
                
                if res_status == 200:
                    res_json = json.loads(res_text)
                    insight = res_json['candidates'][0]['content']['parts'][0]['text']
                    msg = f"🔔 <b>{feed['name']}</b>\n\n{insight}\n\n<a href='{entry['link']}'>원문 보기</a>"
                    t_url = f"https://api.telegram.org/bot{token}/sendMessage"
                    t_data = json.dumps({"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
                    await fetch_url(t_url, method="POST", body=t_data, headers={"Content-Type": "application/json"})
                    await env.NEWS_KV.put(entry['id'], "true")
        except: pass
    await log_to_kv(env, "Crawl Finished.")
