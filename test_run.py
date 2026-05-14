import time, feedparser, yaml, requests, sys
from analyzer import NewsAnalyzer

# Set encoding for Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_single_news():
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    analyzer = NewsAnalyzer(config['gemini_api_key'])
    
    print("가장 최신 뉴스를 가져오는 중...")
    feed_url = config['feeds'][0]['url']
    d = feedparser.parse(feed_url)
    
    if not d.entries:
        print("뉴스를 가져오지 못했습니다.")
        return

    entry = d.entries[0]
    print(f"분석 중: {entry.title}")
    
    analysis = analyzer.analyze(entry.title, entry.summary)
    
    message = (
        f"🚀 <b>[테스트 속보 분석]</b>\n\n"
        f"<b>원문</b>: {entry.title}\n\n"
        f"{analysis}\n\n"
        f"🔗 <a href='{entry.link}'>기사 원문 보기</a>"
    )
    
    url = f"https://api.telegram.org/bot{config['telegram']['token']}/sendMessage"
    payload = {
        "chat_id": config['telegram']['chat_id'],
        "text": message,
        "parse_mode": "HTML"
    }
    
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("✅ 텔레그램으로 테스트 메시지를 성공적으로 보냈습니다!")
    else:
        print(f"❌ 발송 실패: {response.text}")

if __name__ == "__main__":
    test_single_news()
