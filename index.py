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
    {"name": "Handelsblatt", "url": "https://www.handelsblatt.com/contentexport/feed/top-themen/"},
    {"name": "X-Bloomberg", "url": "https://nitter.perennialte.ch/WalterBloomberg/rss"},
    {"name": "X-Deltaone", "url": "https://nitter.perennialte.ch/DeItaone/rss"},
    {"name": "X-Spectator", "url": "https://nitter.perennialte.ch/spectatorindex/rss"}
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
    # Replace all newlines with a space to prevent tall cells in Excel (limit to 2-3 visual rows)
    t = re.sub(r'\s*\n\s*', ' ', t)
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
                if any(kw in (entry['title'] + entry['description']) for kw in ["이민재", "한국경제TV", "한경TV", "hankyung"]): continue
                g_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
                prompt = f"""당신은 프로 기자를 위한 '글로벌 마켓 인텔리전스 비서'입니다. 
당신의 임무는 해외 속보를 분석하여 기자가 단독/기획 기사를 빠르게 작성할 수 있도록 핵심 인사이트를 브리핑하는 것입니다.

[브리핑 가이드라인]
1. 리포트 제목이나 서두에 '한국경제TV' 등 특정 매체명을 언급하지 마세요. 바로 분석 본론으로 들어갑니다.
2. 기사 작성을 위한 '단서' 제공: 단순 요약을 넘어 기자가 취재 방향을 잡을 수 있는 예리한 관점을 제시하세요.
3. 쩐널리즘(Jjournalism) 강화: 독특한 자본의 흐름이나 투자 팁 등 기사화하기 좋은 '돈 되는 이야기'를 발굴하세요.
4. 속도감 있는 워딩: 전문가가 전문가에게 보고하듯 간결하고 명확한 문체를 사용하세요.

[출력 형식]
- [핵심 브리핑]: 뉴스의 본질과 시장이 주목해야 할 이유 (1~2문장).
- [기획/취재 포인트]: 기자가 심층 취재하거나 질문해야 할 핵심 쟁점.
- [글로벌 자본 흐름]: 증권/거시/산업 관점에서의 실질적인 영향 분석.
- [리스크 & 기회]: 투자자가 놓치기 쉬운 변수와 대응 전략.

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
            csv = "\ufeff\"매체          \",\"날짜          \",\"제목                                        \",\"링크            \",\"요약\"\n"
            for item in data:
                # Clean on-the-fly for existing data
                date_val = item.get('date', '').replace("/", ".")
                if len(date_val) > 11: date_val = date_val[-11:]
                
                title = clean_for_csv(item.get('title', ''))
                summary = clean_for_csv(item.get('summary', ''))
                link_formula = f'=HYPERLINK("{item["link"]}","▶ 원문보기")'
                r = [
                    item['source'].strip(),
                    " " + date_val.strip(),
                    title.strip().ljust(50),
                    link_formula,
                    summary.strip()
                ]
                csv += ",".join([f'"{str(v).replace("\"", "\"\"")}"' for v in r]) + "\n"
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
                if text.startswith("/"):
                    text = text.split("@")[0]
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
                elif text == "/setup":
                    await env.NEWS_KV.put("KEY_TELEGRAM_CHAT_ID", str(chat_id))
                    menu = {"commands": [
                        {"command": "crawl", "description": "🚀 실시간 글로벌 뉴스 수집"},
                        {"command": "setup", "description": "⚙️ 현재 방을 알림 수신지로 설정"},
                        {"command": "csv", "description": "📅 리포트(CSV) 다운로드"},
                        {"command": "test", "description": "🧪 AI 분석 성능 테스트"},
                        {"command": "logs", "description": "📋 시스템 로그 확인"}
                    ], "scope": {"type": "chat", "chat_id": chat_id}}
                    await fetch_url(f"https://api.telegram.org/bot{token}/setMyCommands", method="POST", body=menu)
                    msg = "✅ <b>설정 완료!</b>\n\n이 방을 실시간 뉴스 수신지로 등록하고 메뉴판 설정을 마쳤습니다."
                    await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", method="POST", body={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
                elif text == "/test":
                    await fetch_url(f"https://api.telegram.org/bot{token}/sendMessage", method="POST", body={"chat_id": chat_id, "text": "🧪 분석 성능 테스트 중..."})
                    res = await run_crawl_cycle(env, force=True)
                elif text == "/start":
                    menu = {"commands": [
                        {"command": "crawl", "description": "🚀 실시간 글로벌 뉴스 수집"},
                        {"command": "setup", "description": "⚙️ 현재 방을 알림 수신지로 설정"},
                        {"command": "csv", "description": "📅 리포트(CSV) 다운로드"},
                        {"command": "test", "description": "🧪 AI 분석 성능 테스트"},
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
