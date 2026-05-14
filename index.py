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
    val = await env.NEWS_KV.get(f"KEY_{key_name}")
    if val: return val
    try: return getattr(env, key_name, None)
    except: return None

async def fetch_url(url, method="GET", body=None):
    import js
    opt = {"method": method}
    if body:
        opt["method"] = "POST"
        opt["headers"] = {"Content-Type": "application/json"}
        opt["body"] = json.dumps(body)
    js_opt = js.JSON.parse(json.dumps(opt))
    res = await js.fetch(url, js_opt)
    return await res.text(), res.status

def parse_rss(xml_content):
    try:
        root = ET.fromstring(xml_content)
        items = []
        for item in root.findall(".//item") or root.findall(".//entry") or root.findall(".//{http://www.w3.org/2005/Atom}entry"):
            def find_text(node, tag):
                for t in [tag, f"{{http://www.w3.org/2005/Atom}}{tag}", f"{{http://purl.org/rss/1.0/}}{tag}"]:
                    found = node.find(t)
                    if found is not None and found.text: return found.text
                return ""
            title = find_text(item, "title") or "Untitled News"
            link = ""
            link_node = item.find("link") or item.find("{http://www.w3.org/2005/Atom}link")
            if link_node is not None:
                link = link_node.get("href") or link_node.text or ""
            description = find_text(item, "description") or find_text(item, "summary") or find_text(item, "content")
            items.append({'title': title.strip(), 'link': link.strip(), 'description': description[:500].strip(), 'id': link or title})
        return items
    except: return []

async def on_fetch(request, env, ctx):
    import js
    path = js.URL.new(request.url).pathname
    if path == "/view-logs":
        logs = await env.NEWS_KV.get("SYSTEM_LOGS")
        return js.Response.new(logs or "No logs.")
    
    # 강제 수집 테스트
    if path == "/test-crawl":
        await log_to_kv(env, "Manual Test Crawl Started")
        token = await get_secure_key(env, "TELEGRAM_TOKEN")
        chat_id = await get_secure_key(env, "TELEGRAM_CHAT_ID")
        gemini_key = await get_secure_key(env, "GEMINI_API_KEY")
        
        feed = DEFAULT_FEEDS[0] # SEC 뉴스 하나만 테스트
        xml, _ = await fetch_url(feed['url'])
        items = parse_rss(xml)
        if items:
            entry = items[0]
            await log_to_kv(env, f"Test News: {entry['title'][:20]}")
            g_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-lite-latest:generateContent?key={gemini_key}"
            p_load = {"contents": [{"parts": [{"text": f"요약하라: {entry['title']}\n{entry['description']}"}]}]}
            res_txt, _ = await fetch_url(g_url, method="POST", body=p_load)
            ans = json.loads(res_txt)['candidates'][0]['content']['parts'][0]['text']
            msg = f"🧪 <b>TEST: {feed['name']}</b>\n\n{ans}\n\n<a href='{entry['link']}'>원문</a>"
            await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", body={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
            return js.Response.new(f"Test message sent for: {entry['title']}")
        return js.Response.new("No news found to test.")

    if request.method == "POST":
        try:
            data = await request.json()
            if "message" in data:
                chat_id = data["message"]["chat"]["id"]
                token = await get_secure_key(env, "TELEGRAM_TOKEN")
                logs = await env.NEWS_KV.get("SYSTEM_LOGS")
                logs_list = json.loads(logs) if logs else ["No logs."]
                msg = "📋 <b>GNS Status:</b>\n\n" + "\n".join(logs_list)
                await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", body={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
            return js.Response.new("OK")
        except: return js.Response.new("Error")
    return js.Response.new("GNS Bot Running.")

async def on_scheduled(event, env, ctx):
    await log_to_kv(env, "Cron: Run Started")
    token = await get_secure_key(env, "TELEGRAM_TOKEN")
    chat_id = await get_secure_key(env, "TELEGRAM_CHAT_ID")
    gemini_key = await get_secure_key(env, "GEMINI_API_KEY")
    for feed in DEFAULT_FEEDS:
        try:
            xml, _ = await fetch_url(feed['url'])
            items = parse_rss(xml)
            for entry in items[:2]:
                if await env.NEWS_KV.get(entry['id']): continue
                await log_to_kv(env, f"Analyzing: {entry['title'][:20]}")
                g_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-lite-latest:generateContent?key={gemini_key}"
                p_load = {"contents": [{"parts": [{"text": f"요약하라: {entry['title']}\n{entry['description']}"}]}]}
                res_txt, res_st = await fetch_url(g_url, method="POST", body=p_load)
                if res_st == 200:
                    ans = json.loads(res_txt)['candidates'][0]['content']['parts'][0]['text']
                    msg = f"🔔 <b>{feed['name']}</b>\n\n{ans}\n\n<a href='{entry['link']}'>원문 보기</a>"
                    await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", body={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
                    await env.NEWS_KV.put(entry['id'], "true")
        except: pass
    await log_to_kv(env, "Cron: Run Finished")
