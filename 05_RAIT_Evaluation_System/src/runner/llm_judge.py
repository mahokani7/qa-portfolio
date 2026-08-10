import random

class LLMJudge:
    def __init__(self, use_mock=True):
        self.use_mock = use_mock

    def evaluate_response(self, prompt, agent_responses):
        """
        실제 운영 시에는 OpenAI API를 연동하여 루브릭 프롬프트로 0~5점을 채점합니다.
        파일럿 단계에서는 검증을 위해 가상(Mock) 데이터를 안정적으로 생성합니다.
        """
        if self.use_mock:
            # 현실적인 테스트를 위해 2.5 ~ 4.8 사이의 무작위 점수 생성
            metrics = ['R', 'E', 'U', 'S', 'T', 'A', 'C', 'P']
            return {m: round(random.uniform(2.5, 5.0), 1) for m in metrics}
        
        else:
            # 오프라인/실제 OpenAI 연동 시 예시 구조
            # from openai import OpenAI
            # client = OpenAI(api_key="YOUR_API_KEY")
            # response = client.chat.completions.create(...)
            pass