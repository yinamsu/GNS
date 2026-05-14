import json
import xml.etree.ElementTree as ET
from datetime import datetime

# 클라우드플레어 네이티브 fetch 사용을 위한 래퍼
async def fetch_url(url, method="GET", body=None, headers=None):
    import js
    options = {"method": method}
    if body:
        options["body"] = body
    if headers:
        options["headers"] = headers
    
    response = await js.fetch(url, js.Object.fromEntries(js.Map.new(options.items())))
    text = await response.text()
    return text, response.status

# RSS 파싱
def parse_rss(xml_content):
    try:
        root = ET.fromstring(xml_content)
        items = []
        for item in root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry"):
            title_node = item.find("title") or item.find("{http://www.w3.org/2005/Atom}title")
            link_node = item.find("link") or item.find("{http://www.w3.org/2005/Atom}link")
            desc_node = item.find("description") or item.find("{http://www.w3.org/2005/Atom}summary")
            
            title = title_node.text if title_node is not None else "No Title"
            link = link_node.get("href") if link_node is not None and link_node.get("href") else (link_node.text if link_node is not None else "")
            description = desc_node.text if desc_node is not None else ""
            
            items.append({'title': title, 'link': link, 'description': description, 'id': link or title})
        return items
    except:
        return []

async def on_scheduled(event, env, ctx):
    print(f"Triggered at {datetime.now()}")
    
    # 1. 설정 로드
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    
    telegram_token = getattr(env, "TELEGRAM_TOKEN", config['telegram']['token'])
    telegram_chat_id = getattr(env, "TELEGRAM_CHAT_ID", config['telegram']['chat_id'])
    gemini_key = getattr(env, "GEMINI_API_KEY", config['gemini_api_key'])

    for feed in config['feeds']:
        try:
            print(f"Checking: {feed['name']}")
            xml_text, status = await fetch_url(feed['url'])
            if status != 200: continue
            
            items = parse_rss(xml_text)
            for entry in items[:3]:
                # 중복 확인
                if await env.NEWS_KV.get(entry['id']): continue
                
                print(f"New: {entry['title']}")
                
                # Gemini REST API 호출 (SDK 없이 직접 호출)
                gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-lite-latest:generateContent?key={gemini_key}"
                prompt = f"금융 전문 기자로서 아래 뉴스를 분석하여 [요약], [기자적 분석], [취재 제언] 형식으로 작성하라.\n\n제목: {entry['title']}\n내용: {entry['description']}"
                
                payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]})
                headers = {"Content-Type": "application/json"}
                
                res_text, res_status = await fetch_url(gemini_url, method="POST", body=payload, headers=headers)
                
                if res_status == 200:
                    res_json = json.loads(res_text)
                    insight = res_json['candidates'][0]['content']['parts'][0]['text'].replace("*", "")
                    
                    # 텔레그램 전송
                    msg = f"🔔 <b>{feed['name']}</b>\n\n{insight}\n\n<a href='{entry['link']}'>원문 보기</a>"
                    t_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
                    t_data = json.dumps({"chat_id": telegram_chat_id, "text": msg, "parse_mode": "HTML"})
                    await fetch_url(t_url, method="POST", body=t_data, headers={"Content-Type": "application/json"})
                    
                    # 읽음 처리
                    await env.NEWS_KV.put(entry['id'], "true")
                    
        except Exception as e:
            print(f"Error: {e}")

    print("Task Done.")
