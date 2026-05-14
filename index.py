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
    method = request.method
    await log_to_kv(env, f"Signal In: {method}")
    
    token = getattr(env, "TELEGRAM_TOKEN", "")
    chat_id = getattr(env, "TELEGRAM_CHAT_ID", "64106898")
    
    if method == "POST":
        try:
            data = await request.json()
            await log_to_kv(env, f"Data: {str(data)[:50]}")
            
            if "message" in data:
                text = data["message"].get("text", "")
                await log_to_kv(env, f"Cmd: {text}")
                
                # 어떤 명령이든 로그 리포트
                logs = await env.NEWS_KV.get("SYSTEM_LOGS")
                logs_list = json.loads(logs) if logs else ["No logs."]
                msg = "📋 <b>Status</b>\n\n" + "\n".join(logs_list)
                
                t_url = f"https://api.telegram.org/bot{token}/sendMessage"
                await fetch_url(t_url, body={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
            
            return js.Response.new("OK")
        except Exception as e:
            await log_to_kv(env, f"Err: {str(e)}")
    
    # 브라우저 접속(GET) 시 테스트 메시지 발송
    if method == "GET":
        t_url = f"https://api.telegram.org/bot{token}/sendMessage"
        await fetch_url(t_url, body={"chat_id": chat_id, "text": "🌐 Browser access detected!"})
        return js.Response.new(f"GNS Running. Token valid: {bool(token)}")

async def on_scheduled(event, env, ctx):
    await log_to_kv(env, "Cron Start")
    # ... (기존 크론 로직 생략 - 일단은 통신부터 잡겠습니다)
    pass
