# 🌐 GNS (Global News System)

**GNS**는 전 세계 주요 금융 및 비즈니스 뉴스를 실시간으로 모니터링하고, Google Gemini 2.5 AI를 통해 핵심 인사이트를 요약 분석하여 텔레그램으로 전달하는 스마트 뉴스 비서입니다.

## ✨ 주요 기능
- **24/7 실시간 모니터링**: Cloudflare Workers의 크론 트립(Cron Trigger)을 사용하여 1분 단위로 전 세계 RSS 피드를 감시합니다.
- **AI 인사이트 분석**: 최신 **Gemini 2.5 Flash-lite** 모델을 활용하여 방대한 뉴스를 [요약], [분석], [제언]의 3단계로 정제합니다.
- **서버리스 아키텍처**: 별도의 서버 유지보수 없이 Cloudflare 인프라 위에서 영구적으로 가동됩니다.
- **제로 디펜던시 (Zero-Dependency)**: 외부 라이브러리 없이 Python 표준 라이브러리만을 사용하여 극한의 안정성과 배포 속도를 보장합니다.
- **KV 기반 데이터 영속성**: Cloudflare KV를 활용하여 뉴스 중복 수집을 방지하고, 시스템 로그 및 API 키를 안전하게 보관합니다.
- **텔레그램 대화형 인터페이스**: `/logs`, `/crawl`, `/test` 등의 명령어를 통해 모바일에서 직접 봇을 제어할 수 있습니다.

## 🛠 기술 스택
- **Runtime**: Cloudflare Workers (Python Environment)
- **AI Engine**: Google Gemini 1.5/2.5 Flash-lite
- **Storage**: Cloudflare Workers KV
- **Communication**: Telegram Bot API (Webhook)
- **Language**: Pure Python 3.13 (Native Library Only)

## ⌨️ 텔레그램 명령어
- `/start`: 봇 초기 설정 및 메뉴판 등록
- `/logs`: 최근 30개의 시스템 활동 로그 확인
- `/crawl`: 즉시 뉴스 수집 및 분석 실행
- `/test`: 최신 뉴스 1건에 대해 중복 무시 강제 분석 실행

---
*Developed by yinam. Designed for Financial Journalists & Analysts.*
