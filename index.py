import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

DEFAULT_FEEDS = [
    {"name": "SEC News", "url": "https://www.sec.gov/news/pressreleases.rss"},
    {"name": "Bloomberg", "url": "https://www.bloomberg.com/feeds/bfinance/most-read.xml"},
    {"name": "Reuters Biz", "url": "https://www.reutersagency.com/feed/?best-topics=business&post_type=best"},
    {"name": "WSJ Markets", "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"},
    {"name": "CNBC Finance", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069"},
    {"name": "FT World", "url": "https://www.ft.com/?format=rss"},
    {"name": "MarketWatch", "url": "http://feeds.marketwatch.com/marketwatch/topstories/"},
    {"name": "Nikkei Asia", "url": "https://asia.nikkei.com/rss/feed/nar"},
    {"name": "Euronews Biz", "url": "https://www.euronews.com/rss?level=vertical&name=business"},
    {"name": "BBC Business", "url": "https://feeds.bbci.co.uk/news/business/rss.xml"}
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
    opt = {"method": method, "headers": {"User-Agent": "Mozilla/5.0"}}
    if body:
        opt["method"] = "POST"
        opt["headers"]["Content-Type"] = "application/json"
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
            link = ""
            l_node = find_tag(item, "link")
            if l_node is not None: link = l_node.get("href") or l_node.text or ""
            if not link:
                g_node = find_tag(item, "guid")
                if g_node is not None and g_node.text and g_node.text.startswith("http"): link = g_node.text
            desc_node = find_tag(item, "description") or find_tag(item, "summary") or find_tag(item, "content")
            desc = desc_node.text if desc_node is not None else ""
            items.append({'title': str(title).strip(), 'link': str(link).strip(), 'description': str(desc)[:500].strip(), 'id': link or title})
        return items
    except: return []

def clean_for_tg(text):
    t = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = t.replace("##", "<b>■</b>").replace("#", "<b>•</b>")
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
            for entry in items[:1]:
                if not force and await env.NEWS_KV.get(entry['id']): continue
                
                g_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
                # 실명 제거 및 전문 분석가 페르소나 강화
                prompt = f"""당신은 '글로벌 수석 금융 분석 에디터'입니다. 
다음 뉴스를 전문적인 금융 리포트 스타일로 분석하세요.

[분석 가이드라인]
1. 거시 경제 흐름과 글로벌 증시/산업에 미칠 실질적 영향 분석.
2. 시장 컨센서스와의 괴리나 투자자 주의 사항(리스크) 강조.
3. 데이터 중심의 통찰력 있는 요약 (불필요한 수식어 배제).
4. 제목은 눈에 띄게, 내용은 [핵심 요약] - [시장 영향] - [투자자 가이드] 순으로 작성.

뉴스 제목: {entry['title']}
뉴스 내용: {entry['description']}
"""
                res_txt, st = await fetch_url(g_url, method="POST", body={"contents": [{"parts": [{"text": prompt}]}]})
                
                if st == 200:
                    ans = json.loads(res_txt)['candidates'][0]['content']['parts'][0]['text']
                    msg = f"🔔 <b>[{feed['name']}]</b>\n\n{clean_for_tg(ans)}"
                    if entry['link']: msg += f"\n\n🔗 <a href='{entry['link']}'>원문 보기 (클릭)</a>"
                    await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", method="POST", body={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
                    
                    archive = await env.NEWS_KV.get("NEWS_ARCHIVE")
                    archive_list = json.loads(archive) if archive else []
                    new_item = {"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "source": feed['name'], "title": entry['title'], "summary": ans[:100].replace("\n", " ").strip(), "link": entry['link']}
                    archive_list.insert(0, new_item)
                    await env.NEWS_KV.put("NEWS_ARCHIVE", json.dumps(archive_list[:500]))
                    if not force: await env.NEWS_KV.put(entry['id'], "true")
        except: pass
    return "Cycle Done"

async def on_fetch(request, env, ctx):
    import js
    try:
        url_str = request.url
        if "/download-csv" in url_str:
            archive = await env.NEWS_KV.get("NEWS_ARCHIVE")
            if not archive: return js.Response.new("No data.")
            data = json.loads(archive)
            csv = "Date,Source,Title,Summary,Link\n"
            for item in data:
                r = [item['date'], item['source'], item['title'], item['summary'], item['link']]
                csv += ",".join([f'"{str(v).replace('"', '""')}"' for v in r]) + "\n"
            headers = {"Content-Type": "text/csv; charset=utf-8", "Content-Disposition": "attachment; filename=gns_report.csv"}
            return js.Response.new(csv, js.JSON.parse(json.dumps({"headers": headers})))

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
                elif text == "/csv":
                    worker_url = js.URL.new(request.url).origin
                    msg = f"📅 <b>전략 리포트 아카이브</b>\n\n최근 기사 리포트 다운로드:\n\n{worker_url}/download-csv"
                    await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", method="POST", body={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
                elif text == "/crawl":
                    await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", method="POST", body={"chat_id": chat_id, "text": "🚀 글로벌 모니터링 수집 중..."})
                    await run_crawl_cycle(env)
                    await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", method="POST", body={"chat_id": chat_id, "text": "✅ 수집 완료."})
                elif text == "/test":
                    await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", method="POST", body={"chat_id": chat_id, "text": "🧪 분석 성능 테스트 중..."})
                    await run_crawl_cycle(env, force=True)
                elif text == "/start":
                    menu = {"commands": [
                        {"command": "logs", "description": "시스템 로그"},
                        {"command": "crawl", "description": "즉시 뉴스 수집"},
                        {"command": "csv", "description": "리포트 다운로드"}
                    ]}
                    await fetch_url(f"https://api.telegram.org/bot{token}/setMyCommands", method="POST", body=menu)
                    await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", method="POST", body={"chat_id": chat_id, "text": "📰 <b>GNS Professional</b> 가동!\n\n메뉴를 확인하세요."})
            return js.Response.new("OK")
        return js.Response.new("GNS is Ready.")
    except Exception as e:
        return js.Response.new(f"CRASH: {str(e)}")

async def on_scheduled(event, env, ctx):
    await run_crawl_cycle(env)
