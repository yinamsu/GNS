import feedparser
import yaml
import json
import requests
import google.generativeai as genai
from datetime import datetime

class NewsAnalyzer:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('models/gemini-flash-lite-latest')

    def analyze(self, title, summary):
        prompt = f"""
        너는 15년 차 베테랑 경제기자야. 아래 해외 뉴스를 보고 한국 금융위원회(FSC) 출입 기자가 '단독' 또는 '기획' 기사를 쓸 수 있도록 분석해줘.
        분석 시 사용자의 실명이나 특정 개인의 이름을 절대 언급하지 마.
        
        [뉴스 제목]: {title}
        [뉴스 요약]: {summary}

        형식:
        1. 한 줄 요약: (핵심 내용)
        2. 국내 시사점: (한국 금융 정책이나 시장에 미칠 영향)
        3. 취재 팁: (기자가 금융위 관계자에게 무엇을 질문해야 할지)
        """
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"AI 분석 중 오류 발생: {e}"

def send_telegram(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram Send Error: {e}")

async def scheduled(event, env, ctx):
    """
    Cloudflare Workers Cron Trigger entry point.
    Runs every minute based on wrangler.toml config.
    """
    token = env.TELEGRAM_TOKEN
    chat_id = env.TELEGRAM_CHAT_ID
    api_key = env.GEMINI_API_KEY
    
    analyzer = NewsAnalyzer(api_key)
    
    # Load seen IDs from KV
    seen_ids_str = await env.NEWS_KV.get("seen_ids")
    if seen_ids_str:
        seen_ids = set(json.loads(seen_ids_str))
        first_run = False
    else:
        seen_ids = set()
        first_run = True

    # Feeds to check (Config could also be in KV or env)
    feeds = [
        {"name": "SEC Press", "url": "https://www.sec.gov/news/pressreleases.rss"},
        {"name": "Bloomberg Finance", "url": "https://www.bloomberg.com/feeds/bfinance/most-read.xml"},
        {"name": "Reuters Business", "url": "https://www.reutersagency.com/feed/?best-topics=business&post_type=best"}
    ]

    new_items_found = False
    for feed in feeds:
        try:
            # Use requests (Cloudflare Workers Python environment supports it)
            resp = requests.get(feed['url'], timeout=15)
            d = feedparser.parse(resp.content)
            
            for entry in d.entries:
                news_id = entry.get('id', entry.link)
                if news_id not in seen_ids:
                    seen_ids.add(news_id)
                    new_items_found = True
                    
                    if not first_run:
                        print(f"New Source Detected: {entry.title}")
                        analysis = analyzer.analyze(entry.title, entry.summary)
                        
                        message = (
                            f"🚀 <b>[글로벌 금융 이슈]</b>\n\n"
                            f"<b>원문:</b> {entry.title}\n\n"
                            f"{analysis}\n\n"
                            f"🔗 <a href='{entry.link}'>기사 원문 보기</a>"
                        )
                        send_telegram(token, chat_id, message)
        except Exception as e:
            print(f"Error fetching {feed['name']}: {e}")

    # Save updated seen IDs to KV if any new items were added
    if new_items_found or first_run:
        await env.NEWS_KV.put("seen_ids", json.dumps(list(seen_ids)))
        if first_run:
            print("Initial synchronization complete.")
