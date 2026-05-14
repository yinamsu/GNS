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

async def fetch_url(url, method="POST", body=None):
    import js
    opt = {"method": method, "headers": {"Content-Type": "application/json"}}
    if body: opt["body"] = json.dumps(body)
    js_opt = js.JSON.parse(json.dumps(opt))
    res = await js.fetch(url, js_opt)
    return await res.text(), res.status

async def on_fetch(request, env, ctx):
    import js
    # 모든 변수 이름 확인 (디버깅용)
    try:
        keys = js.Object.keys(env)
        await log_to_kv(env, f"Available Keys: {list(keys)}")
    except: pass

    # 변수 가져오기 (가장 확실한 방법들 시도)
    token = getattr(env, "TELEGRAM_TOKEN", None) or env.TELEGRAM_TOKEN
    chat_id = getattr(env, "TELEGRAM_CHAT_ID", "64106898") or env.TELEGRAM_CHAT_ID
    
    valid = bool(token)
    await log_to_kv(env, f"Token Check: {valid}")

    if request.method == "POST":
        try:
            if valid:
                data = await request.json()
                msg = f"📩 Signal: {str(data)[:50]}"
                t_url = f"https://api.telegram.org/bot{token}/sendMessage"
                await fetch_url(t_url, body={"chat_id": chat_id, "text": msg})
            return js.Response.new("OK")
        except:
            return js.Response.new("Error")
    
    if request.method == "GET":
        if valid:
            t_url = f"https://api.telegram.org/bot{token}/sendMessage"
            await fetch_url(t_url, body={"chat_id": chat_id, "text": "✅ Server Linked!"})
        return js.Response.new(f"GNS Running. Token valid: {valid}")

async def on_scheduled(event, env, ctx):
    pass
