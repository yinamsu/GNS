import google.generativeai as genai

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
