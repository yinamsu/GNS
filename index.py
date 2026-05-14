import json
import xml.etree.ElementTree as ET
from datetime import datetime

# 1. 뉴스 피드 설정
DEFAULT_FEEDS = [
    {"name": "SEC Press", "url": "https://www.sec.gov/news/pressreleases.rss"},
    {"name": "Bloomberg Finance", "url": "https://www.bloomberg.com/feeds/bfinance/most-read.xml"},
    {"name": "Reuters Business", "url": "https://www.reutersagency.com/feed/?best-topics=business&post_type=best"}
]

# 2. 유틸리티 함수
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
    # KV에서 먼저 찾고 없으면 환경변수 확인
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

# 3. 메인 핸들러 (HTTP 요청 처리)
async def on_fetch(request, env, ctx):
    import js
    try:
        url = js.URL.new(request.url)
        if url.pathname == "/view-logs":
            logs = await env.NEWS_KV.get("SYSTEM_LOGS")
            return js.Response.new(logs or "No logs yet.", headers={"Content-Type": "application/json"})
        
        if request.method == "POST":
            data = await request.json()
            if "message" in data:
                token = await get_secure_key(env, "TELEGRAM_TOKEN")
                chat_id = data["message"]["chat"]["id"]
                logs = await env.NEWS_KV.get("SYSTEM_LOGS")
                logs_list = json.loads(logs) if logs else ["No logs."]
                msg = "📋 <b>GNS Logs:</b>\n\n" + "\n".join(logs_list)
                await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", body={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
            return js.Response.new("OK")
        
        return js.Response.new("GNS News Bot is Alive!")
    except Exception as e:
        return js.Response.new(f"Internal Error: {str(e)}", status=500)

# 4. 스케줄러 핸들러 (1분마다 실행)
async def on_scheduled(event, env, ctx):
    await log_to_kv(env, "Cron: Run Started")
    token = await get_secure_key(env, "TELEGRAM_TOKEN")
    chat_id = await get_secure_key(env, "TELEGRAM_CHAT_ID")
    gemini_key = await get_secure_key(env, "GEMINI_API_KEY")

    if not token or not chat_id or not gemini_key:
        await log_to_kv(env, "Cron Error: Missing Keys in KV!")
        return

    for feed in DEFAULT_FEEDS:
        try:
            xml_text, status = await fetch_url(feed['url'])
            if status != 200: continue
            
            items = parse_rss(xml_text)
            for entry in items[:2]:
                if await env.NEWS_KV.get(entry['id']): continue
                
                await log_to_kv(env, f"Analyzing: {entry['title'][:20]}")
                gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-lite-latest:generateContent?key={gemini_key}"
                prompt = f"금융 전문 기자로서 아래 뉴스를 요약/분석하라: {entry['title']}\n{entry['description']}"
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                
                res_str, res_status = await fetch_url(gemini_url, method="POST", body=payload)
                if res_status == 200:
                    insight = json.loads(res_str)['candidates'][0]['content']['parts'][0]['text']
                    msg = f"🔔 <b>{feed['name']}</b>\n\n{insight}\n\n<a href='{entry['link']}'>원문 보기</a>"
                    await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", body={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
                    await env.NEWS_KV.put(entry['id'], "true")
        except Exception as e:
            await log_to_kv(env, f"Error in {feed['name']}: {str(e)}")
    
    await log_to_kv(env, "Cron: Run Finished")
