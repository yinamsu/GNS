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
    {"name": "Nikkei Asia", "url": "https://asia.nikkei.com/rss/feed/nar"},
    {"name": "Japan Times", "url": "https://www.japantimes.co.jp/news_category/business/feed/"},
    {"name": "Euronews Biz", "url": "https://www.euronews.com/rss?level=vertical&name=business"},
    {"name": "BBC Business", "url": "https://feeds.bbci.co.uk/news/business/rss.xml"},
    {"name": "Handelsblatt", "url": "https://www.handelsblatt.com/contentexport/feed/top-themen/"}
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

def clean_for_csv(text):
    import re
    # Remove markdown bold/header symbols
    t = re.sub(r'[*#\-]', '', text)
    # Normalize multiple newlines
    t = re.sub(r'\n+', '\n', t)
    return t.strip()

async def run_crawl_cycle(env, force=False):
    token = await get_secure_key(env, "TELEGRAM_TOKEN")
    chat_id = await get_secure_key(env, "TELEGRAM_CHAT_ID")
    gemini_key = await get_secure_key(env, "GEMINI_API_KEY")
    model = await get_secure_key(env, "GEMINI_MODEL", "gemini-2.5-flash-lite")
    if not token or not chat_id or not gemini_key: return "Keys Missing"

    count = 0
    for feed in DEFAULT_FEEDS:
        try:
            xml, _ = await fetch_url(feed['url'])
            items = parse_rss(xml)
            targets = items[:1]
            for entry in targets:
                if not force and await env.NEWS_KV.get(entry['id']): continue
                if "이민재" in entry['title'] or "이민재" in entry['description']: continue
                g_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
                prompt = f"""당신은 '글로벌 수석 금융 분석 에디터'이자 증권·경제 전문 기자입니다. 
다음 뉴스를 한국경제TV 독자들을 위한 심도 있는 금융 리포트 스타일로 분석하세요.

[분석 페르소나 & 가이드라인]
1. 증권 분석: 종목별 목표주가 변동, MSCI 편입 등 수급 이슈, 실적 전망 등을 예리하게 짚어주세요.
2. 거시 경제: 인플레이션, Fed 금리 전망, 지정학적 리스크가 국내외 증시에 미칠 영향을 분석하세요.
3. 쩐널리즘(Jjournalism): 가상자산(크립토), 스캠 방지, 실질적인 재테크 팁 등 독자에게 유익한 '돈' 이야기를 포함하세요.
4. 리스크 강조: 시장 컨센서스와의 괴리나 투자자가 놓치기 쉬운 잠재적 위험을 강조하세요.

[출력 형식]
- [핵심 요약]: 뉴스의 핵심을 1~2문장으로 정리.
- [심층 분석]: 증권/거시/산업적 관점에서의 상세 분석.
- [시장 영향 & 리스크]: 투자자가 주의해야 할 점과 향후 전망.
- [투자자 가이드]: 전문 기자의 시각으로 제안하는 대응 전략.

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
                    summary_clean = clean_for_csv(ans[:500])
                    new_item = {"date": datetime.now().strftime(" %m.%d %H:%M"), "source": feed['name'], "title": entry['title'], "summary": summary_clean, "link": entry['link']}
                    archive_list.insert(0, new_item)
                    await env.NEWS_KV.put("NEWS_ARCHIVE", json.dumps(archive_list[:500]))
                    if not force: await env.NEWS_KV.put(entry['id'], "true")
                    count += 1
                    if force: return f"성공: {entry['title'][:15]}"
        except: pass
    return f"Processed {count} feeds."

async def on_fetch(request, env, ctx):
    import js
    try:
        url_str = request.url
        if "/download-csv" in url_str:
            archive = await env.NEWS_KV.get("NEWS_ARCHIVE")
            if not archive: return js.Response.new("No data.")
            data = json.loads(archive)
            csv = "\ufeff매체,날짜,제목,링크,요약\n"
            for item in data:
                # Clean on-the-fly for existing data
                date_val = item.get('date', '').replace("/", ".")
                if len(date_val) > 11: date_val = date_val[-11:]
                if not date_val.startswith(" "): date_val = " " + date_val
                
                title = clean_for_csv(item.get('title', ''))
                summary = clean_for_csv(item.get('summary', ''))
                # Excel hyperlink formula: =HYPERLINK("url","display_text") - no spaces!
                link_formula = f'=HYPERLINK("{item["link"]}","▶ 원문보기")'
                r = [item['source'], date_val, title, link_formula, summary]
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
                    res = await run_crawl_cycle(env)
                    await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", method="POST", body={"chat_id": chat_id, "text": f"✅ {res}"})
                elif text == "/test":
                    await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", method="POST", body={"chat_id": chat_id, "text": "🧪 분석 성능 테스트 중..."})
                    res = await run_crawl_cycle(env, force=True)
                elif text == "/start":
                    menu = {"commands": [
                        {"command": "crawl", "description": "🚀 실시간 글로벌 뉴스 수집"},
                        {"command": "test", "description": "🧪 AI 분석 성능 테스트"},
                        {"command": "csv", "description": "📅 리포트(CSV) 다운로드"},
                        {"command": "logs", "description": "📋 시스템 로그 확인"}
                    ]}
                    await fetch_url(f"https://api.telegram.org/bot{token}/setMyCommands", method="POST", body=menu)
                    welcome = "📰 <b>GNS Professional</b> 가동!\n\n아래 <b>메뉴 버튼</b>을 눌러 4개의 명령어를 확인하세요."
                    await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", method="POST", body={"chat_id": chat_id, "text": welcome, "parse_mode": "HTML"})
            return js.Response.new("OK")
        return js.Response.new("GNS is Ready.")
    except Exception as e:
        return js.Response.new(f"CRASH: {str(e)}")

async def on_scheduled(event, env, ctx):
    await run_crawl_cycle(env)
