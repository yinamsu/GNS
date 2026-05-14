import json
import xml.etree.ElementTree as ET
from datetime import datetime

# 수집할 피드 목록
DEFAULT_FEEDS = [
    {"name": "SEC Press", "url": "https://www.sec.gov/news/pressreleases.rss"},
    {"name": "Bloomberg Finance", "url": "https://www.bloomberg.com/feeds/bfinance/most-read.xml"},
    {"name": "Reuters Business", "url": "https://www.reutersagency.com/feed/?best-topics=business&post_type=best"}
]

async def log_to_kv(env, message):
    ts = datetime.now().strftime("%H:%M:%S")
    full = f"[{ts}] {message}"
    print(full)
    try:
        logs = await env.NEWS_KV.get("SYSTEM_LOGS")
        logs_list = json.loads(logs) if logs else []
        logs_list.insert(0, full)
        await env.NEWS_KV.put("SYSTEM_LOGS", json.dumps(logs_list[:30]))
    except: pass

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
                    logs_list = json.loads(logs) if logs else ["No logs recorded yet."]
                    response_text = "📋 <b>GNS Status Log</b>\n\n" + "\n".join(logs_list)
                    
                    token = getattr(env, "TELEGRAM_TOKEN", None) or env.TELEGRAM_TOKEN
                    t_url = f"https://api.telegram.org/bot{token}/sendMessage"
                    await fetch_url(t_url, body={"chat_id": chat_id, "text": response_text, "parse_mode": "HTML"})
            return js.Response.new("OK")
        except: return js.Response.new("Error")
    
    return js.Response.new("GNS News Bot is Running!")

async def on_scheduled(event, env, ctx):
    await log_to_kv(env, "Cron: Starting News Crawl")
    
    token = getattr(env, "TELEGRAM_TOKEN", None) or env.TELEGRAM_TOKEN
    chat_id = getattr(env, "TELEGRAM_CHAT_ID", None) or env.TELEGRAM_CHAT_ID
    gemini_key = getattr(env, "GEMINI_API_KEY", None) or env.GEMINI_API_KEY

    for feed in DEFAULT_FEEDS:
        try:
            # RSS 가져오기
            res_text, status = await fetch_url(feed['url'], method="GET")
            if status != 200: continue
            
            items = parse_rss(res_text)
            for entry in items[:2]: # 각 피드당 최신 2개만 분석
                if await env.NEWS_KV.get(entry['id']): continue
                
                await log_to_kv(env, f"Analyzing: {entry['title'][:20]}...")
                
                # Gemini 분석
                gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-lite-latest:generateContent?key={gemini_key}"
                prompt = f"금융 전문 기자로서 아래 뉴스를 분석하여 [요약], [기자적 분석], [취재 제언] 형식으로 한국어로 작성하라.\n\n제목: {entry['title']}\n내용: {entry['description']}"
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                
                res_json_str, res_status = await fetch_url(gemini_url, method="POST", body=payload)
                if res_status != 200: 
                    await log_to_kv(env, f"Gemini API Error: {res_status}")
                    continue
                
                res_json = json.loads(res_json_str)
                insight = res_json['candidates'][0]['content']['parts'][0]['text'].replace("*", "")
                
                # 텔레그램 전송
                msg = f"🔔 <b>{feed['name']}</b>\n\n{insight}\n\n<a href='{entry['link']}'>원문 보기</a>"
                t_url = f"https://api.telegram.org/bot{token}/sendMessage"
                await fetch_url(t_url, body={"chat_id": chat_id, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": False})
                
                # 읽음 처리
                await env.NEWS_KV.put(entry['id'], "true")
                
        except Exception as e:
            await log_to_kv(env, f"Error in {feed['name']}: {str(e)}")

    await log_to_kv(env, "Cron: Crawl Finished")
