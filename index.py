import os
import yaml
import requests
import google.generativeai as genai
import xml.etree.ElementTree as ET
from datetime import datetime

# RSS 파싱을 위한 간단한 함수 (feedparser 대체)
def parse_rss(xml_content):
    try:
        root = ET.fromstring(xml_content)
        items = []
        # RSS 2.0 (item) 또는 Atom (entry) 지원
        for item in root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry"):
            title_node = item.find("title") or item.find("{http://www.w3.org/2005/Atom}title")
            link_node = item.find("link") or item.find("{http://www.w3.org/2005/Atom}link")
            desc_node = item.find("description") or item.find("{http://www.w3.org/2005/Atom}summary")
            
            title = title_node.text if title_node is not None else "No Title"
            # Atom link는 보통 속성(href)에 있음
            if link_node is not None:
                link = link_node.get("href") if link_node.get("href") else link_node.text
            else:
                link = ""
            
            description = desc_node.text if desc_node is not None else ""
            
            items.append({
                'title': title,
                'link': link,
                'description': description,
                'id': link or title
            })
        return items
    except Exception as e:
        print(f"Parsing error: {e}")
        return []

async def on_scheduled(event, env, ctx):
    print(f"Scheduled event triggered at {datetime.now()}")
    
    # 1. 설정 및 API 키 로드 (Secrets 우선)
    telegram_token = getattr(env, "TELEGRAM_TOKEN", None)
    telegram_chat_id = getattr(env, "TELEGRAM_CHAT_ID", None)
    gemini_key = getattr(env, "GEMINI_API_KEY", None)
    
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    telegram_token = telegram_token or config['telegram']['token']
    telegram_chat_id = telegram_chat_id or config['telegram']['chat_id']
    gemini_key = gemini_key or config['gemini_api_key']
    
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('gemini-1.5-flash-lite-latest')

    # 2. 뉴스 수집 및 분석
    for feed in config['feeds']:
        try:
            print(f"Fetching feed: {feed['name']}")
            response = requests.get(feed['url'], timeout=10)
            items = parse_rss(response.content)
            
            for entry in items[:3]:  # 최신 3개만 확인
                # 중복 확인 (KV 사용)
                is_seen = await env.NEWS_KV.get(entry['id'])
                if is_seen: continue
                
                print(f"New entry found: {entry['title']}")
                
                # AI 분석
                prompt = f"""
                금융 전문 기자로서 아래 뉴스를 분석하여 '취재 인사이트'를 작성하라.
                
                제목: {entry['title']}
                내용: {entry['description']}
                
                형식:
                <b>[요약]</b> (한 줄 요약)
                <b>[기자적 분석]</b> (시장 영향 및 주요 체크 포인트)
                <b>[취재 제언]</b> (이 뉴스에서 파생될 수 있는 추가 취재 거리 또는 질문 2가지)
                """
                
                response = model.generate_content(prompt)
                insight = response.text.replace("*", "") # 마크다운 별표 제거
                
                # 텔레그램 전송
                msg = f"🔔 <b>{feed['name']}</b>\n\n{insight}\n\n<a href='{entry['link']}'>원문 보기</a>"
                t_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
                requests.post(t_url, data={"chat_id": telegram_chat_id, "text": msg, "parse_mode": "HTML"})
                
                # 읽음 처리 (KV 저장)
                await env.NEWS_KV.put(entry['id'], "true")
                
        except Exception as e:
            print(f"Error processing {feed['name']}: {e}")

    print("Scheduled task completed.")
