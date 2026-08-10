"""
knowledge_base.py
- 교육과정 안내 챗봇(Service Agent) 및 AI 평가자(Judge Agent)가 참조하는 기준 정보를 다룹니다.
- 기준 정보(정책 문서)는 코드에 하드코딩하지 않고, 사용자가 업로드한 여러 개의 파일(.txt/.md/.docx/.pdf)에서
  읽어와 [청크 분할 -> 임베딩 -> ChromaDB 저장 -> 유사도 검색] 순서의 RAG 방식으로 Service Agent에 제공합니다.
- 평가 기준(EVALUATION_CRITERIA)도 별도 JSON 파일에서 로드합니다.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

import chromadb
from chromadb.utils import embedding_functions
from docx import Document
from pypdf import PdfReader

from config import (
    OPENAI_API_KEY,
    KNOWLEDGE_UPLOAD_DIR,
    EVALUATION_CRITERIA_FILE,
    CHROMA_DB_DIR,
    CHROMA_COLLECTION_NAME,
    EMBEDDING_MODEL,
    RAG_CHUNK_SIZE,
    RAG_CHUNK_OVERLAP,
    RAG_TOP_K,
)

SUPPORTED_EXTENSIONS = {".txt", ".md", ".docx", ".pdf"}


# ---------------------------------------------------------------------------
# 1. 파일 입력: 텍스트 추출
# ---------------------------------------------------------------------------

def read_document_text(file_path) -> str:
    """.txt/.md/.docx/.pdf 파일에서 순수 텍스트를 추출합니다."""
    file_path = Path(file_path)
    ext = file_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"지원하지 않는 파일 형식입니다: {ext} (지원 형식: {', '.join(sorted(SUPPORTED_EXTENSIONS))})"
        )

    if ext == ".docx":
        document = Document(str(file_path))
        paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
        return "\n".join(paragraphs)

    if ext == ".pdf":
        reader = PdfReader(str(file_path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(p.strip() for p in pages if p.strip())

    return file_path.read_text(encoding="utf-8")


def prompt_for_knowledge_file() -> Path:
    """콘솔에서 사용자로부터 직접 지식 파일 경로를 입력받습니다. (CLI 대화형 전용)"""
    while True:
        user_input = input(
            "\n[Knowledge Base] 추가할 기준정보 파일 경로를 입력하세요 (.txt/.md/.docx/.pdf): "
        ).strip().strip('"')
        candidate = Path(user_input)
        if candidate.exists() and candidate.suffix.lower() in SUPPORTED_EXTENSIONS:
            return candidate
        print(f"[Warning] 유효하지 않은 경로이거나 지원하지 않는 형식입니다: {user_input}")


# ---------------------------------------------------------------------------
# 2. 텍스트 청크 분할
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = RAG_CHUNK_SIZE, overlap: int = RAG_CHUNK_OVERLAP) -> List[str]:
    """
    지식 텍스트를 검색 단위(청크)로 분할합니다.
    - '[섹션 제목]' 형태의 구분자가 있으면 섹션 단위로 우선 분리합니다. (의미 단위 보존)
    - 섹션(또는 구분자가 없는 전체 텍스트)이 chunk_size보다 길면 overlap을 둔 슬라이딩 윈도우로 재분할합니다.
    """
    text = text.strip()
    if not text:
        return []

    sections = re.split(r"\n(?=\[[^\]]+\])", text)
    sections = [s.strip() for s in sections if s.strip()]
    if not sections:
        sections = [text]

    chunks: List[str] = []
    for section in sections:
        if len(section) <= chunk_size:
            chunks.append(section)
            continue
        start = 0
        while start < len(section):
            end = start + chunk_size
            piece = section[start:end].strip()
            if piece:
                chunks.append(piece)
            start = end - overlap
    return chunks


# ---------------------------------------------------------------------------
# 3. ChromaDB 기반 RAG 인덱스 (다중 파일 업로드 지원)
# ---------------------------------------------------------------------------

def get_chroma_collection():
    """업로드된 지식 파일들의 임베딩을 저장하는 ChromaDB 영구 컬렉션을 반환합니다."""
    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    embed_fn = embedding_functions.OpenAIEmbeddingFunction(
        api_key=OPENAI_API_KEY, model_name=EMBEDDING_MODEL
    )
    return client.get_or_create_collection(name=CHROMA_COLLECTION_NAME, embedding_function=embed_fn)


def list_uploaded_knowledge_files() -> List[Path]:
    """현재 업로드되어 있는 지식 파일 목록을 반환합니다."""
    if not KNOWLEDGE_UPLOAD_DIR.exists():
        return []
    return sorted(
        (p for p in KNOWLEDGE_UPLOAD_DIR.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS),
        key=lambda p: p.name,
    )


def add_file_to_chroma(file_path, collection=None) -> int:
    """
    파일 하나를 청크 분할하여 ChromaDB에 추가합니다.
    동일한 파일명의 청크가 이미 있으면 먼저 지우고 다시 추가합니다 (재업로드 시 중복 방지).

    :return: 추가된 청크 개수
    """
    file_path = Path(file_path)
    collection = collection or get_chroma_collection()

    text = read_document_text(file_path)
    chunks = chunk_text(text)
    if not chunks:
        return 0

    collection.delete(where={"source": file_path.name})
    ids = [f"{file_path.name}::{i}" for i in range(len(chunks))]
    metadatas = [{"source": file_path.name, "chunk_index": i} for i in range(len(chunks))]
    collection.add(documents=chunks, ids=ids, metadatas=metadatas)
    return len(chunks)


def remove_knowledge_file(filename: str) -> None:
    """업로드 폴더에서 지식 파일을 삭제합니다. ChromaDB 반영은 rebuild_chroma_index()로 별도 수행해야 합니다."""
    target = KNOWLEDGE_UPLOAD_DIR / filename
    if target.exists():
        target.unlink()


def rebuild_chroma_index() -> Dict[str, int]:
    """
    ChromaDB 컬렉션을 완전히 비우고, 업로드 폴더에 현재 남아 있는 파일들로 처음부터 다시 구축합니다.
    파일 삭제로 발생한 잔존 임베딩을 정리할 때 사용합니다.

    :return: {파일명: 청크 개수} 딕셔너리
    """
    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    try:
        client.delete_collection(CHROMA_COLLECTION_NAME)
    except Exception:
        pass  # 컬렉션이 아직 없으면 무시하고 새로 생성

    embed_fn = embedding_functions.OpenAIEmbeddingFunction(
        api_key=OPENAI_API_KEY, model_name=EMBEDDING_MODEL
    )
    collection = client.get_or_create_collection(name=CHROMA_COLLECTION_NAME, embedding_function=embed_fn)

    result: Dict[str, int] = {}
    for file_path in list_uploaded_knowledge_files():
        result[file_path.name] = add_file_to_chroma(file_path, collection=collection)
    return result


def retrieve_context(query: str, top_k: int = RAG_TOP_K, collection=None) -> List[str]:
    """질문과 가장 유사한 상위 top_k개의 청크를 ChromaDB에서 검색합니다."""
    collection = collection or get_chroma_collection()
    if collection.count() == 0:
        return []

    n_results = min(top_k, collection.count())
    results = collection.query(query_texts=[query], n_results=n_results)
    documents = results.get("documents") or [[]]
    return documents[0]


# ---------------------------------------------------------------------------
# 4. 평가 기준(Judge Agent용 구조화 데이터) 로드
# ---------------------------------------------------------------------------

def load_evaluation_criteria(file_path: Optional[str] = None) -> dict:
    """Judge Agent가 사용할 카테고리별 평가 기준(policy/allowed_keywords)을 JSON 파일에서 읽어옵니다."""
    criteria_file = Path(file_path) if file_path else EVALUATION_CRITERIA_FILE
    if not criteria_file.exists():
        raise FileNotFoundError(
            f"평가 기준 파일을 찾을 수 없습니다: {criteria_file}. "
            "카테고리별 policy/allowed_keywords를 담은 JSON 파일을 준비해주세요."
        )
    return json.loads(criteria_file.read_text(encoding="utf-8"))


# 모듈 독립 실행 테스트: 콘솔에서 지식 파일 경로를 입력받아 ChromaDB에 추가하고 검색을 시연합니다.
if __name__ == "__main__":
    print("--- Knowledge Base (ChromaDB RAG) 테스트 ---")
    if not OPENAI_API_KEY:
        raise SystemExit("[Error] OpenAI API Key가 설정되지 않았습니다. .env 파일을 확인해주세요.")

    source_file = prompt_for_knowledge_file()
    dest = KNOWLEDGE_UPLOAD_DIR / source_file.name
    if source_file.resolve() != dest.resolve():
        dest.write_bytes(Path(source_file).read_bytes())

    n_chunks = add_file_to_chroma(dest)
    print(f"[Info] '{dest.name}' 파일에서 {n_chunks}개 청크를 ChromaDB에 추가했습니다.")

    print("\n--- 현재 업로드된 지식 파일 목록 ---")
    for f in list_uploaded_knowledge_files():
        print(f" - {f.name}")

    print("\n--- 평가 기준(JSON) 로드 확인 ---")
    criteria = load_evaluation_criteria()
    for category, info in criteria.items():
        print(f"[{category}] 필수 키워드 예시: {info['allowed_keywords']}")

    test_question = "지각을 세 번 하면 어떻게 되나요?"
    print(f"\n--- 검색 테스트 (질문: {test_question}) ---")
    for i, chunk in enumerate(retrieve_context(test_question), 1):
        print(f"\n[검색된 청크 {i}]\n{chunk}")
