# Global News Scrapper (GNS) 🚀

금융 기자를 위한 **실시간 글로벌 금융 속보 모니터링 및 AI 분석 시스템**입니다. 전 세계 주요 금융당국과 매체의 소스를 1분 단위로 동시 수집하여, 15년 차 시니어 경제기자의 시각으로 재해석한 인사이트를 텔레그램으로 즉시 배달합니다.

## 🌟 주요 기능
- **초고속 실시간 감시**: Cloudflare Workers를 통해 1분마다 전 세계 RSS 피드를 동시(Parallel) 수집합니다.
- **AI 베테랑 기자의 인사이트**: Gemini 2.0 Flash-Lite 모델이 단순 요약을 넘어 '국내 시장 시사점'과 '구체적인 취재 팁'을 제안합니다.
- **서버리스 아키텍처**: 서버 관리 없이 클라우드플레어 엣지에서 24시간 안정적으로 가동됩니다.
- **중복 알림 방지**: Cloudflare KV 저장소를 활용하여 이미 처리된 뉴스는 다시 알리지 않습니다.

## 🛠 기술 스택
- **Runtime**: Cloudflare Workers (Python)
- **AI**: Google Gemini AI (gemini-flash-lite-latest)
- **Database**: Cloudflare KV (Key-Value Storage)
- **Notification**: Telegram Bot API
- **CI/CD**: GitHub Actions / Cloudflare Integration

## 🚀 배포 및 설정 가이드

### 1. 깃허브 저장소 연결
이 레포지토리를 본인의 GitHub 계정에 Fork 하거나 복사한 뒤, Cloudflare 대시보드에서 **Workers & Pages > Create > Workers > Connect to Git**을 통해 연결하세요.

### 2. KV Namespace 생성 및 바인딩
뉴스 읽음 상태를 저장하기 위해 KV 저장소가 필요합니다.
1. Cloudflare 대시보드에서 **Workers & Pages > KV > Create a namespace** 클릭
2. 이름을 `NEWS_KV`로 생성
3. 생성된 **ID**를 복사하여 `wrangler.toml`의 `[[kv_namespaces]]` 섹션에 업데이트하거나, 워커 설정의 **Settings > Variables > KV Namespace Bindings**에서 직접 연결하세요.

### 3. 환경 변수(Secrets) 설정
워커의 **Settings > Variables > Environment Variables**에서 아래 항목들을 등록하세요.
- `TELEGRAM_TOKEN`: 텔레그램 봇 토큰
- `TELEGRAM_CHAT_ID`: 알림을 받을 텔레그램 Chat ID
- `GEMINI_API_KEY`: 구글 Gemini API 키

### 4. 자동 배포
이제 코드에 수정사항이 생겨 GitHub에 `push`하면, Cloudflare가 자동으로 빌드하여 실시간으로 반영합니다.

## 📈 수집 소스 (기본값)
- **SEC Press Releases**: 미국 증권거래위원회 보도자료
- **Bloomberg Finance**: 블룸버그 금융 속보
- **Reuters Business**: 로이터 비즈니스 뉴스
- *(추가 가능: `src/index.py` 내 `feeds` 리스트 수정)*

## 📝 라이선스
MIT License
