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

async def get_secure_key(env, key_name, default=None):
    val = await env.NEWS_KV.get(f"KEY_{key_name}")
    if val: return val
    try: return getattr(env, key_name, default)
    except: return default

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
            title = find_text(item, "title") or "Untitled"
            link = ""
            lnode = item.find("link") or item.find("{http://www.w3.org/2005/Atom}link")
            if lnode is not None: link = lnode.get("href") or lnode.text or ""
            desc = find_text(item, "description") or find_text(item, "summary") or find_text(item, "content")
            items.append({'title': title.strip(), 'link': link.strip(), 'description': desc[:500].strip(), 'id': link or title})
        return items
    except: return []

def safe_html(text):
    # 텔레그램 HTML 모드에서 에러를 유발하는 문자들 제거
    return text.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;").replace("*", "")

async def on_fetch(request, env, ctx):
    import js
    try:
        url_str = request.url
        if "/view-logs" in url_str:
            logs = await env.NEWS_KV.get("SYSTEM_LOGS")
            return js.Response.new(logs or "No logs.")
        
        if request.method == "POST":
            # 가장 안전한 방식으로 바디 읽기
            raw = await request.text()
            data = json.loads(raw)
            await log_to_kv(env, f"Cmd Received")
            
            if "message" in data:
                chat_id = data["message"]["chat"]["id"]
                token = await get_secure_key(env, "TELEGRAM_TOKEN")
                logs = await env.NEWS_KV.get("SYSTEM_LOGS")
                logs_list = json.loads(logs) if logs else ["No logs."]
                msg = "📋 <b>GNS Status Log:</b>\n\n" + "\n".join(logs_list)
                await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", method="POST", body={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
            return js.Response.new("OK")
            
        return js.Response.new("GNS Bot is Running.")
    except Exception as e:
        await log_to_kv(env, f"Fetch Error: {str(e)}")
        return js.Response.new(f"CRASH: {str(e)}")

async def on_scheduled(event, env, ctx):
    await log_to_kv(env, "Cron Start")
    token = await get_secure_key(env, "TELEGRAM_TOKEN")
    chat_id = await get_secure_key(env, "TELEGRAM_CHAT_ID")
    gemini_key = await get_secure_key(env, "GEMINI_API_KEY")
    model = await get_secure_key(env, "GEMINI_MODEL", "gemini-2.5-flash-lite")
    if not token or not chat_id or not gemini_key: return

    for feed in DEFAULT_FEEDS:
        try:
            xml, _ = await fetch_url(feed['url'])
            items = parse_rss(xml)
            for entry in items[:2]:
                if await env.NEWS_KV.get(entry['id']): continue
                
                await log_to_kv(env, f"News: {entry['title'][:20]}")
                g_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
                prompt = f"금융 분석(한국어 요약): {entry['title']}\n{entry['description']}"
                res_txt, st = await fetch_url(g_url, method="POST", body={"contents": [{"parts": [{"text": prompt}]}]})
                
                if st == 200:
                    ans = json.loads(res_txt)['candidates'][0]['content']['parts'][0]['text']
                    # HTML 안전 처리 추가
                    clean_ans = safe_html(ans)
                    msg = f"🔔 <b>{feed['name']}</b>\n\n{clean_ans}\n\n<a href='{entry['link']}'>원문 보기</a>"
                    await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", method="POST", body={"chat_id": chat_id, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": False})
                    await env.NEWS_KV.put(entry['id'], "true")
        except Exception as e:
            await log_to_kv(env, f"Err: {str(e)[:50]}")
    await log_to_kv(env, "Cron Done")
