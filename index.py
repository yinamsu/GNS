import json
import xml.etree.ElementTree as ET
from datetime import datetime

DEFAULT_FEEDS = [
    {"name": "SEC Press", "url": "https://www.sec.gov/news/pressreleases.rss"},
    {"name": "Bloomberg Finance", "url": "https://www.bloomberg.com/feeds/bfinance/most-read.xml"},
    {"name": "Reuters Business", "url": "https://www.reutersagency.com/feed/?best-topics=business&post_type=best"}
]

async def log_to_kv(env, message):
    ts = datetime.now().strftime("%H:%M:%S")
    full = f"[{ts}] {message}"
    try:
        logs = await env.NEWS_KV.get("SYSTEM_LOGS")
        logs_list = json.loads(logs) if logs else []
        logs_list.insert(0, full)
        await env.NEWS_KV.put("SYSTEM_LOGS", json.dumps(logs_list[:30]))
    except: pass

async def get_secure_key(env, key_name):
    # 1. 환경 변수 확인
    val = getattr(env, key_name, None)
    if val: return val
    # 2. KV 저장소 확인 (지워짐 방지용)
    return await env.NEWS_KV.get(f"KEY_{key_name}")

async def fetch_url(url, method="POST", body=None):
    import js
    opt = {"method": method, "headers": {"Content-Type": "application/json"}}
    if body: opt["body"] = json.dumps(body)
    js_opt = js.JSON.parse(json.dumps(opt))
    res = await js.fetch(url, js_opt)
    return await res.text(), res.status

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
            data = await request.json()
            if "message" in data and "text" in data["message"]:
                text = data["message"]["text"]
                chat_id = data["message"]["chat"]["id"]
                
                if text == "/logs" or text == "/start":
                    logs = await env.NEWS_KV.get("SYSTEM_LOGS")
                    logs_list = json.loads(logs) if logs else ["No logs."]
                    msg = "📋 <b>GNS Logs</b>\n\n" + "\n".join(logs_list)
                    
                    token = await get_secure_key(env, "TELEGRAM_TOKEN")
                    if token:
                        t_url = f"https://api.telegram.org/bot{token}/sendMessage"
                        await fetch_url(t_url, body={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
            return js.Response.new("OK")
        except: return js.Response.new("Error")
    return js.Response.new("GNS News Bot Running (KV-Key Support)")

async def on_scheduled(event, env, ctx):
    await log_to_kv(env, "Cron: Start")
    
    token = await get_secure_key(env, "TELEGRAM_TOKEN")
    chat_id = await get_secure_key(env, "TELEGRAM_CHAT_ID")
    gemini_key = await get_secure_key(env, "GEMINI_API_KEY")

    if not token or not chat_id or not gemini_key:
        await log_to_kv(env, "Error: Missing Keys in KV or Env!")
        return

    for feed in DEFAULT_FEEDS:
        try:
            res_text, status = await fetch_url(feed['url'], method="GET")
            if status != 200: continue
            
            items = parse_rss(res_text)
            for entry in items[:2]:
                if await env.NEWS_KV.get(entry['id']): continue
                
                await log_to_kv(env, f"Analyzing: {entry['title'][:20]}")
                
                gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-lite-latest:generateContent?key={gemini_key}"
                payload = {"contents": [{"parts": [{"text": f"분석하라: {entry['title']}\n{entry['description']}"}]}]}
                
                res_json_str, res_status = await fetch_url(gemini_url, method="POST", body=payload)
                if res_status == 200:
                    res_json = json.loads(res_json_str)
                    insight = res_json['candidates'][0]['content']['parts'][0]['text']
                    msg = f"🔔 <b>{feed['name']}</b>\n\n{insight}\n\n<a href='{entry['link']}'>원문 보기</a>"
                    t_url = f"https://api.telegram.org/bot{token}/sendMessage"
                    await fetch_url(t_url, body={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
                    await env.NEWS_KV.put(entry['id'], "true")
        except Exception as e:
            await log_to_kv(env, f"Error: {str(e)}")
    await log_to_kv(env, "Cron: Finished")
