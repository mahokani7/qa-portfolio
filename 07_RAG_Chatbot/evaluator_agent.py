import json
import re
from pathlib import Path
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
EVAL_PROMPT_PATH = BASE_DIR / "ai_answer.md"


def load_eval_prompt() -> str:
    return EVAL_PROMPT_PATH.read_text(encoding="utf-8")


def parse_evaluation_output(text: str) -> dict:
    scores = {}

    score_match = re.search(r"<점수>(.*?)</점수>", text, re.DOTALL)
    if score_match:
        pairs = re.findall(r"(\w+):\s*(\d+(?:\.\d+)?)", score_match.group(1))
        for name, val in pairs:
            scores[name] = float(val)

    final_match = re.search(r"<최종점수>(.*?)</최종점수>", text, re.DOTALL)
    final_score = float(final_match.group(1).strip()) if final_match else 0.0

    rubric_match = re.search(r"<rubric 평가>(.*?)</rubric 평가>", text, re.DOTALL)
    reason = rubric_match.group(1).strip() if rubric_match else text.strip()

    accuracy = scores.get("정확성", 0)
    grounding = scores.get("이해도", 0)

    return {
        "accuracy_score": int(accuracy),
        "grounding_score": int(grounding),
        "hallucination": False,
        "source_match": True,
        "overall_pass": final_score >= 4.0,
        "reason": reason,
        "evaluation_scores": scores,
        "final_score": final_score,
        "raw_output": text,
    }


def get_evaluation_from_openai(
    user_question: str,
    ai_answer: str,
    expected_answer: str,
    expected_source: str,
    retrieved_sources: list,
    retrieved_contexts: list,
):
    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)

    eval_framework = load_eval_prompt()

    prompt = f"""{eval_framework}

---

## 평가 대상

### Chat History ###
사용자: `{user_question}`
어시스턴트: `{ai_answer}`

위 평가 기준과 출력 형식에 따라 평가하십시오.
"""

    response = llm.invoke(prompt)

    try:
        return parse_evaluation_output(response.content)
    except Exception as error:
        return {
            "accuracy_score": 0,
            "grounding_score": 0,
            "hallucination": True,
            "source_match": False,
            "overall_pass": False,
            "reason": f"평가 파싱 오류: {error}",
            "raw_response": response.content,
        }
