# 🌐 GNS Professional (Global Market Intelligence Assistant)

**GNS Professional**은 프로 기자를 위한 **글로벌 마켓 인텔리전스 비서**입니다. 전 세계 주요 금융, 비즈니스, 테크 뉴스를 실시간으로 모니터링하고, AI를 통해 기자가 단독/기획 기사를 빠르게 작성할 수 있도록 핵심 인사이트와 취재 포인트를 브리핑합니다.

## ✨ 핵심 기능

### 1. 초고속 글로벌 모니터링 (High-Speed Monitoring)
- **글로벌 인텔리전스 채널**: SEC, Bloomberg, Reuters, FT, WSJ, Nikkei Asia, Handelsblatt 등 주요 10개 이상의 글로벌 매체를 24/7 감시합니다.
- **실시간 인사이트**: Cloudflare Workers 스케줄러를 통해 전 세계의 핫 이슈를 포착 즉시 분석하여 보고합니다.

### 2. 기자를 위한 인텔리전스 브리핑 (Reporter Intelligence)
- **마켓 인사이더 페르소나**: 단순 요약을 넘어 기자가 취재 방향을 잡을 수 있는 예리한 관점과 [기획/취재 포인트]를 제시합니다.
- **철저한 자사 뉴스 필터링**: 한국경제TV(한경TV)의 기사가 중복 수집되지 않도록 스마트 필터링 로직이 적용되어 있어, 오직 외부 소스 분석에만 집중합니다.
- **매체 중립적 브리핑**: 특정 언론사 명칭 없이 핵심 본론과 글로벌 자본의 흐름을 중심으로 신속하게 브리핑합니다.

### 3. 전략 리포트 아카이브 (CSV Export)
- **엑셀 최적화 (Excel-Ready)**:
    - **세로 높이 최적화**: 분석문의 불필요한 줄바꿈을 제거하여 셀 높이를 컴팩트하게 유지 (2~3행 이내)
    - **열 너비 및 포맷팅**: 엑셀 초기 오픈 시 가독성을 위한 헤더 패딩 및 날짜 표시 오류(`#######`) 방지 로직 적용
    - **=HYPERLINK**: 수식 적용으로 엑셀에서 즉시 원문 이동 가능

### 4. 텔레그램 통합 관제 (Control Center)
- **/crawl**: 즉시 글로벌 채널 뉴스 수집 및 인텔리전스 분석
- **/csv**: 분석된 리포트 아카이브 다운로드 (엑셀 최적화 버전)
- **/setup**: 현재 채팅방을 실시간 알림 수신지로 설정
- **/logs**: 시스템 운영 상태 및 활동 로그 실시간 확인

## 🛠 기술 스택
- **Runtime**: Cloudflare Workers (Python Environment)
- **AI Engine**: Google Gemini 2.5 Flash-lite (Journalist Intelligence Mode)
- **Storage**: Cloudflare Workers KV (State & Key Management)
- **Communication**: Telegram Bot API

---
*Developed for Pro Journalists. Stay Ahead of the Global Market with GNS.*
