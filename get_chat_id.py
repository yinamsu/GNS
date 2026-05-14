import requests
import yaml
import sys

# Set encoding to utf-8 for Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def get_chat_id():
    try:
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        token = config['telegram']['token']
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        
        print(f"텔레그램 서버에서 최신 메시지를 확인 중입니다... (토큰: {token[:10]}...)")
        response = requests.get(url, timeout=10).json()
        
        if not response.get("ok"):
            print(f"API 오류 발생: {response.get('description')}")
            return

        results = response.get("result", [])
        if not results:
            print("메시지 내역이 비어 있습니다. 텔레그램 앱에서 봇에게 메시지를 보낸 후 잠시(1~2초) 뒤에 다시 실행해 보세요.")
            return

        # 가장 최근 메시지에서 chat id 추출
        for update in reversed(results):
            if "message" in update:
                chat_id = update["message"]["chat"]["id"]
                user_name = update["message"]["chat"].get("first_name", "User")
                print(f"확인된 Chat ID: {chat_id} ({user_name}님)")
                print(f"이 ID를 config.yaml의 chat_id 항목에 붙여넣으세요.")
                return
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    get_chat_id()
