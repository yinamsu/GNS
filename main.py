import asyncio
import aiohttp
import feedparser
import yaml
import json
import os
import time
from analyzer import NewsAnalyzer

async def fetch_feed(session, feed_info):
    """개별 피드를 비동기적으로 수집합니다."""
    try:
        async with session.get(feed_info['url'], timeout=15) as response:
            content = await response.read()
            d = feedparser.parse(content)
            return {'name': feed_info['name'], 'entries': d.entries}
    except Exception as e:
        print(f"[{feed_info['name']}] 수집 오류: {e}")
        return {'name': feed_info['name'], 'entries': []}

async def send_telegram_async(config, text):
    """텔레그램 메시지를 비동기적으로 발송합니다."""
    url = f"https://api.telegram.org/bot{config['telegram']['token']}/sendMessage"
    payload = {"chat_id": config['telegram']['chat_id'], "text": text, "parse_mode": "HTML"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                return await response.json()
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")

async def main():
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    analyzer = NewsAnalyzer(config['gemini_api_key'])
    
    if os.path.exists('seen_news.json'):
        with open('seen_news.json', 'r', encoding='utf-8') as f:
            try:
                seen_ids = set(json.load(f))
            except:
                seen_ids = set()
    else:
        seen_ids = set()
    
    first_run = not seen_ids
    print(f"시스템 시작 (초기 모드: {'OFF' if not first_run else 'ON'})", flush=True)

    async with aiohttp.ClientSession(headers={'User-Agent': 'Mozilla/5.0'}) as session:
        while True:
            start_time = time.time()
            print(f"[{time.ctime()}] 전 세계 소스 동시 수집 중...", flush=True)
            
            # 모든 피드를 동시에 수집
            tasks = [fetch_feed(session, f) for f in config['feeds']]
            feeds_results = await asyncio.gather(*tasks)
            
            for result in feeds_results:
                for entry in result['entries']:
                    news_id = entry.get('id', entry.link)
                    if news_id not in seen_ids:
                        seen_ids.add(news_id)
                        
                        if not first_run:
                            # [속도 최적화] 신규 소스 발견 즉시 처리
                            print(f"🚀 신규 소식 발견: {entry.title}", flush=True)
                            
                            # AI 분석
                            analysis = analyzer.analyze(entry.title, entry.summary)
                            
                            message = (
                                f"🚀 <b>[글로벌 금융 이슈]</b>\n\n"
                                f"<b>원문:</b> {entry.title}\n\n"
                                f"{analysis}\n\n"
                                f"🔗 <a href='{entry.link}'>기사 원문 보기</a>"
                            )
                            await send_telegram_async(config, message)
                            await asyncio.sleep(1) # 전송 간 짧은 간격
            
            # 읽은 뉴스 저장
            with open('seen_news.json', 'w', encoding='utf-8') as f:
                json.dump(list(seen_ids), f, ensure_ascii=False, indent=4)
            
            if first_run:
                print("초기 데이터 동기화 완료. 다음 루프부터 실시간 알림이 시작됩니다.", flush=True)
                first_run = False

            # 실행 시간 계산 후 대기
            elapsed = time.time() - start_time
            sleep_time = max(0, config.get('interval', 60) - elapsed)
            print(f"대기 중... ({int(sleep_time)}초 뒤 다음 체크)", flush=True)
            await asyncio.sleep(sleep_time)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("시스템을 종료합니다.", flush=True)
