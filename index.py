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
            def find_tag(node, tag):
                for t in [tag, f"{{http://www.w3.org/2005/Atom}}{tag}", f"{{http://purl.org/rss/1.0/}}{tag}"]:
                    found = node.find(t)
                    if found is not None: return found
                return None
            
            title_node = find_tag(item, "title")
            title = title_node.text if title_node is not None else "Untitled"
            
            # 링크 찾기 강화
            link = ""
            l_node = find_tag(item, "link")
            if l_node is not None:
                link = l_node.get("href") or l_node.text or ""
            
            # 만약 그래도 링크가 없다면 guid 등에서 찾기
            if not link:
                g_node = find_tag(item, "guid")
                if g_node is not None and g_node.text and g_node.text.startswith("http"):
                    link = g_node.text

            desc_node = find_tag(item, "description") or find_tag(item, "summary") or find_tag(item, "content")
            desc = desc_node.text if desc_node is not None else ""
            
            items.append({'title': str(title).strip(), 'link': str(link).strip(), 'description': str(desc)[:500].strip(), 'id': link or title})
        return items
    except: return []

def clean_for_tg(text):
    # HTML 특수문자 치환 및 마크다운 기호 정리
    t = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = t.replace("##", "<b>■</b>").replace("#", "<b>•</b>")
    t = t.replace("**", "") # 굵게 표시 제거 (HTML로 처리할 것이므로)
    return t

async def run_crawl_cycle(env, force=False):
    token = await get_secure_key(env, "TELEGRAM_TOKEN")
    chat_id = await get_secure_key(env, "TELEGRAM_CHAT_ID")
    gemini_key = await get_secure_key(env, "GEMINI_API_KEY")
    model = await get_secure_key(env, "GEMINI_MODEL", "gemini-2.5-flash-lite")
    if not token or not chat_id or not gemini_key: return "Keys Missing"

    for feed in DEFAULT_FEEDS:
        try:
            xml, _ = await fetch_url(feed['url'])
            items = parse_rss(xml)
            targets = items[:1] if force else items[:2]
            for entry in targets:
                if not force and await env.NEWS_KV.get(entry['id']): continue
                
                g_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
                prompt = f"금융 전문 기자로서 요약/분석하라:\n{entry['title']}\n{entry['description']}"
                res_txt, st = await fetch_url(g_url, method="POST", body={"contents": [{"parts": [{"text": prompt}]}]})
                
                if st == 200:
                    ans = json.loads(res_txt)['candidates'][0]['content']['parts'][0]['text']
                    msg = f"🔔 <b>{feed['name']}</b>\n\n{clean_for_tg(ans)}"
                    if entry['link']:
                        # 링크가 있을 때만 확실하게 추가
                        msg += f"\n\n🔗 <a href='{entry['link']}'>원문 보기 (클릭)</a>"
                    
                    await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", method="POST", body={"chat_id": chat_id, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": False})
                    if not force: await env.NEWS_KV.put(entry['id'], "true")
                    if force: return f"성공: {entry['title'][:15]}"
        except: pass
    return "Done"

async def on_fetch(request, env, ctx):
    import js
    try:
        url_str = request.url
        if "/view-logs" in url_str:
            logs = await env.NEWS_KV.get("SYSTEM_LOGS")
            return js.Response.new(logs or "No logs.")
        
        if request.method == "POST":
            raw = await request.text()
            data = json.loads(raw)
            if "message" in data:
                text = data["message"].get("text", "")
                chat_id = data["message"]["chat"]["id"]
                token = await get_secure_key(env, "TELEGRAM_TOKEN")
                if text == "/logs":
                    logs = await env.NEWS_KV.get("SYSTEM_LOGS")
                    logs_list = json.loads(logs) if logs else ["No logs."]
                    msg = "📋 <b>GNS Logs:</b>\n\n" + "\n".join(logs_list)
                    await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", method="POST", body={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
                elif text == "/crawl":
                    await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", method="POST", body={"chat_id": chat_id, "text": "🚀 즉시 수집..."})
                    res = await run_crawl_cycle(env)
                    await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", method="POST", body={"chat_id": chat_id, "text": f"✅ {res}"})
                elif text == "/test":
                    await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", method="POST", body={"chat_id": chat_id, "text": "🧪 테스트 분석 중..."})
                    res = await run_crawl_cycle(env, force=True)
                    await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", method="POST", body={"chat_id": chat_id, "text": f"✅ {res}"})
                elif text == "/start":
                    menu = {"commands": [{"command": "logs", "description": "로그"}, {"command": "crawl", "description": "수집"}, {"command": "test", "description": "테스트"}]}
                    await fetch_url(f"https://api.telegram.org/bot{token}/setMyCommands", method="POST", body=menu)
                    await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", method="POST", body={"chat_id": chat_id, "text": "👋 시작합니다!"})
            return js.Response.new("OK")
        return js.Response.new("GNS Running.")
    except Exception as e:
        return js.Response.new(f"CRASH: {str(e)}")

async def on_scheduled(event, env, ctx):
    await run_crawl_cycle(env)
