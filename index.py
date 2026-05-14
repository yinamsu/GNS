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
        # 네임스페이스 무시를 위해 태그 이름만 추출하는 방식
        root = ET.fromstring(xml_content)
        items = []
        # RSS 2.0 (item) 또는 Atom (entry) 모두 대응
        for item in root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry") or root.findall(".//entry"):
            # 태그 검색 (네임스페이스 포함/미포함 모두 시도)
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
            
            items.append({
                'title': title.strip(),
                'link': link.strip(),
                'description': description[:500].strip(), # 너무 길면 자름
                'id': link or title
            })
        return items
    except Exception as e:
        return []

async def on_fetch(request, env, ctx):
    import js
    if "/view-logs" in request.url:
        logs = await env.NEWS_KV.get("SYSTEM_LOGS")
        return js.Response.new(logs or "No logs yet.")

    if request.method == "POST":
        try:
            raw = await request.text()
            data = json.loads(raw)
            if "message" in data:
                chat_id = data["message"]["chat"]["id"]
                token = await get_secure_key(env, "TELEGRAM_TOKEN")
                logs = await env.NEWS_KV.get("SYSTEM_LOGS")
                logs_list = json.loads(logs) if logs else ["No logs."]
                msg = "📋 <b>GNS Status:</b>\n\n" + "\n".join(logs_list)
                await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", body={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
            return js.Response.new("OK")
        except: return js.Response.new("Error")
    return js.Response.new("GNS News Bot is Running!")

async def on_scheduled(event, env, ctx):
    await log_to_kv(env, "Cron: Starting Crawl")
    token = await get_secure_key(env, "TELEGRAM_TOKEN")
    chat_id = await get_secure_key(env, "TELEGRAM_CHAT_ID")
    gemini_key = await get_secure_key(env, "GEMINI_API_KEY")

    if not token or not chat_id or not gemini_key:
        await log_to_kv(env, "Cron Error: Missing Keys!")
        return

    for feed in DEFAULT_FEEDS:
        try:
            xml, status = await fetch_url(feed['url'])
            if status != 200: continue
            items = parse_rss(xml)
            for entry in items[:2]:
                if await env.NEWS_KV.get(entry['id']): continue
                
                await log_to_kv(env, f"News: {entry['title'][:30]}")
                
                g_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-lite-latest:generateContent?key={gemini_key}"
                prompt = f"금융 전문 기자로서 아래 뉴스를 요약/분석하라:\n제목: {entry['title']}\n내용: {entry['description']}"
                p_load = {"contents": [{"parts": [{"text": prompt}]}]}
                
                res_txt, res_st = await fetch_url(g_url, method="POST", body=p_load)
                if res_st == 200:
                    ans = json.loads(res_txt)['candidates'][0]['content']['parts'][0]['text']
                    msg = f"🔔 <b>{feed['name']}</b>\n\n{ans}\n\n<a href='{entry['link']}'>원문 보기</a>"
                    await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", body={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
                    await env.NEWS_KV.put(entry['id'], "true")
                else:
                    await log_to_kv(env, f"Gemini API Error: {res_st}")
        except Exception as e:
            await log_to_kv(env, f"Feed Error ({feed['name']}): {str(e)[:50]}")
    await log_to_kv(env, "Cron: Finished")
