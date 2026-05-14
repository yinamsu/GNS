import json
import xml.etree.ElementTree as ET
from datetime import datetime

DEFAULT_FEEDS = [
    {"name": "SEC Press", "url": "https://www.sec.gov/news/pressreleases.rss"},
    {"name": "Bloomberg Finance", "url": "https://www.bloomberg.com/feeds/bfinance/most-read.xml"},
    {"name": "Reuters Business", "url": "https://www.reutersagency.com/feed/?best-topics=business&post_type=best"}
]

# KV에 로그 저장 (최신 30줄 유지)
async def log_to_kv(env, message):
    timestamp = datetime.now().strftime("%m-%d %H:%M:%S")
    full_log = f"[{timestamp}] {message}"
    print(full_log) # 대시보드 로그용
    
    try:
        current_logs = await env.NEWS_KV.get("SYSTEM_LOGS")
        logs_list = json.loads(current_logs) if current_logs else []
        logs_list.insert(0, full_log)
        logs_list = logs_list[:30] # 30줄만 유지
        await env.NEWS_KV.put("SYSTEM_LOGS", json.dumps(logs_list))
    except: pass

async def fetch_url(url, method="GET", body=None, headers=None):
    import js
    options = {"method": method}
    if body: options["body"] = body
    if headers: options["headers"] = headers
    response = await js.fetch(url, js.Object.fromEntries(js.Map.new(options.items())))
    return await response.text(), response.status

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

# 텔레그램 명령어 처리 (Webhook 대응)
async def on_fetch(request, env, ctx):
    if request.method == "POST":
        try:
            body = await request.json()
            if "message" in body and "text" in body["message"]:
                text = body["message"]["text"]
                chat_id = body["message"]["chat"]["id"]
                
                if text == "/logs":
                    logs = await env.NEWS_KV.get("SYSTEM_LOGS")
                    logs_list = json.loads(logs) if logs else ["No logs found."]
                    response_text = "📋 <b>최근 로그 30줄</b>\n\n" + "\n".join(logs_list)
                    
                    token = getattr(env, "TELEGRAM_TOKEN", "")
                    t_url = f"https://api.telegram.org/bot{token}/sendMessage"
                    t_data = json.dumps({"chat_id": chat_id, "text": response_text, "parse_mode": "HTML"})
                    await fetch_url(t_url, method="POST", body=t_data, headers={"Content-Type": "application/json"})
                    return js.Response.new("OK", status=200)
        except: pass
    
    import js
    return js.Response.new("GNS Worker is Running", status=200)

async def on_scheduled(event, env, ctx):
    await log_to_kv(env, "Starting scheduled news crawl...")
    
    token = getattr(env, "TELEGRAM_TOKEN", None)
    chat_id = getattr(env, "TELEGRAM_CHAT_ID", None)
    gemini_key = getattr(env, "GEMINI_API_KEY", None)

    for feed in DEFAULT_FEEDS:
        try:
            xml_text, status = await fetch_url(feed['url'])
            if status != 200: continue
            
            items = parse_rss(xml_text)
            for entry in items[:3]:
                if await env.NEWS_KV.get(entry['id']): continue
                
                await log_to_kv(env, f"New post: {entry['title'][:20]}...")
                
                gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-lite-latest:generateContent?key={gemini_key}"
                payload = json.dumps({"contents": [{"parts": [{"text": f"분석하라: {entry['title']}\n{entry['description']}"}]}]})
                
                res_text, res_status = await fetch_url(gemini_url, method="POST", body=payload, headers={"Content-Type": "application/json"})
                if res_status != 200: continue
                
                res_json = json.loads(res_text)
                insight = res_json['candidates'][0]['content']['parts'][0]['text']
                
                msg = f"🔔 <b>{feed['name']}</b>\n\n{insight}\n\n<a href='{entry['link']}'>원문 보기</a>"
                t_url = f"https://api.telegram.org/bot{token}/sendMessage"
                t_data = json.dumps({"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
                await fetch_url(t_url, method="POST", body=t_data, headers={"Content-Type": "application/json"})
                
                await env.NEWS_KV.put(entry['id'], "true")
                
        except Exception as e:
            await log_to_kv(env, f"Error in {feed['name']}: {str(e)[:50]}")

    await log_to_kv(env, "Crawl finished.")
