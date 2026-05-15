# 🌐 GNS Professional (Global News System)

**GNS Professional**은 전 세계 주요 금융, 비즈니스, 테크 뉴스를 실시간으로 모니터링하고, 최첨단 AI(Gemini 2.5)를 통해 전문 기자 수준의 심층 분석 리포트를 생성하는 스마트 뉴스 자동화 시스템입니다.

## ✨ 핵심 기능

### 1. 전 세계 경제 지형 모니터링 (Global Coverage)
- **미국/유럽/일본 등 글로벌 채널**: SEC, Bloomberg, Reuters, FT, WSJ, Nikkei Asia, Japan Times, Handelsblatt, BBC 등 주요 10개 이상의 글로벌 매체를 24/7 감시합니다.
- **실시간 크롤링**: Cloudflare Workers의 스케줄러를 통해 지연 없이 최신 속보를 포착합니다.

### 2. 전문 기자급 AI 심층 분석 (Reporter-Centric AI)
- **전문가 페르소나**: 단순 요약을 넘어 증권부 기자의 시각으로 [핵심 요약] - [심층 분석] - [시장 영향 & 리스크] - [투자자 가이드]를 도출합니다.
- **맞춤형 필터링**: 사용자의 취재 편의를 위해 본인의 기사가 중복 분석되지 않도록 스마트 필터링 로직이 적용되어 있습니다.

### 3. 전략 리포트 아카이브 (CSV Export)
- **CSV 리포트 다운로드**: 지난 24시간 동안 수집된 모든 뉴스를 하나의 CSV 파일로 내려받을 수 있습니다.
- **엑셀 최적화 (Excel-Ready)**:
    - **UTF-8 BOM** 적용으로 한글 깨짐 완벽 방지
    - **=HYPERLINK** 수식 적용으로 엑셀에서 즉시 원문 이동 가능
    - **가독성 중심 열 배치**: 날짜, 매체, 제목, 링크, 요약 순으로 최적화
    - **세로 높이 최적화**: 분석 요약문의 불필요한 줄바꿈을 제거하여 셀 높이를 컴팩트하게 유지 (2~3행 이내)
    - **열 너비 최적화**: 엑셀 초기 오픈 시 가독성을 위한 헤더 패딩 및 제목 열 너비 확보
    - **날짜 표시 오류 방지**: 날짜 열의 ####### 표시 방지를 위한 데이터 포맷팅 적용

### 4. 텔레그램 통합 관제
- **/start**: 시스템 초기화 및 메뉴 자동 등록
- **/crawl**: 즉시 전 세계 채널 뉴스 수집 및 분석
- **/csv**: 분석된 리포트 아카이브 다운로드 링크 생성
- **/test**: AI 분석 성능 강제 테스트 (중복 무시)
- **/logs**: 시스템 운영 상태 및 활동 로그 확인

## 🛠 기술 스택
- **Runtime**: Cloudflare Workers (Python Environment)
- **AI Engine**: Google Gemini 2.5 Flash-lite (Multimodal ready)
- **Storage**: Cloudflare Workers KV (State & Key Management)
- **Communication**: Telegram Bot API
- **Language**: Python 3.13 (Serverless optimized)

---
*Developed for Pro Journalists & Analysts. Stay Ahead of the Global Market.*
