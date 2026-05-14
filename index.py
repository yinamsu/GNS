import json
import xml.etree.ElementTree as ET
from datetime import datetime

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
    # 1. KV 우선 확인 (가장 확실함)
    val = await env.NEWS_KV.get(f"KEY_{key_name}")
    if val: return val
    # 2. 환경 변수 확인
    try: return getattr(env, key_name, None)
    except: return None

async def send_telegram(token, chat_id, text):
    import js
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "HTML"}
    opt = {"method": "POST", "headers": {"Content-Type": "application/json"}, "body": json.dumps(payload)}
    await js.fetch(url, js.JSON.parse(json.dumps(opt)))

async def on_fetch(request, env, ctx):
    import js
    url_obj = js.URL.new(request.url)
    path = url_obj.pathname

    # 비상구: 브라우저에서 바로 로그 보기
    if path == "/view-logs":
        logs = await env.NEWS_KV.get("SYSTEM_LOGS")
        return js.Response.new(logs or "No logs yet.", headers={"Content-Type": "application/json"})

    if request.method == "POST":
        try:
            data = await request.json()
            if "message" in data:
                chat_id = data["message"]["chat"]["id"]
                token = await get_secure_key(env, "TELEGRAM_TOKEN")
                logs = await env.NEWS_KV.get("SYSTEM_LOGS")
                logs_list = json.loads(logs) if logs else ["No logs."]
                await send_telegram(token, chat_id, "📋 <b>Current Logs:</b>\n\n" + "\n".join(logs_list))
            return js.Response.new("OK")
        except: return js.Response.new("Error")
    
    return js.Response.new("GNS Bot is Alive. Access /view-logs to see status.")

async def on_scheduled(event, env, ctx):
    await log_to_kv(env, "Cron: Run Started")
    token = await get_secure_key(env, "TELEGRAM_TOKEN")
    chat_id = await get_secure_key(env, "TELEGRAM_CHAT_ID")
    gemini_key = await get_secure_key(env, "GEMINI_API_KEY")

    if not token or not chat_id or not gemini_key:
        await log_to_kv(env, "Cron Error: Missing Keys in KV!")
        return

    # ... (뉴스 크롤링 로직은 그대로 유지)
    await log_to_kv(env, "Cron: Run Finished")
