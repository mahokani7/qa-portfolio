"""
knowledge_base.py
- 교육과정 안내 챗봇이 참조하는 기준 정보
- 업로드된 지식 파일을 간단 검색해 답변 생성에 사용할 수 있는 지식 소스
"""

import re
from pathlib import Path

# TODO: 실제 교육과정 정책 정보로 채우기 (data/test_cases.json의 expected_policy와 매칭)
COURSE_POLICY = {
    "총_교육시간": "320시간",
    "지각_기준": "지각 3회 = 결석 1일",
    "수료_출석_기준": "전체 훈련시간의 80퍼센트 이상 출석",
    "취업지원_내용": "취업 상담, 이력서 첨삭, 모의면접 지원",
    "안내_외_질문_응답": "확인할 수 없습니다. 교육과정 관련 문의를 부탁드립니다.",
    "부적절_요청_응답": "죄송하지만 해당 요청은 도와드릴 수 없습니다.",
}

KNOWLEDGE_UPLOAD_DIR = Path(__file__).resolve().parent / "data" / "knowledge" / "uploads"
CHROMA_DIR = Path(__file__).resolve().parent / "data" / "chroma"
CHROMA_COLLECTION = "knowledge_files"
SUPPORTED_KNOWLEDGE_EXTENSIONS = {".txt", ".md", ".docx", ".pdf"}
STOPWORDS = {
    "이",
    "그",
    "저",
    "수",
    "몇",
    "좀",
    "관련",
    "알려",
    "알려줘",
    "주세요",
    "되나요",
    "하나요",
    "있나요",
    "어떻게",
    "무엇",
    "어디",
    "어디에",
    "대한",
    "에서",
    "으로",
    "에게",
    "하고",
    "하면",
}
TOKEN_SUFFIXES = (
    "인가요",
    "되나요",
    "하나요",
    "입니다",
    "습니까",
    "나요",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "에",
    "의",
    "로",
    "과",
    "와",
)


def get_policy(key: str) -> str:
    """정책 키로 기준 정보 조회"""
    return COURSE_POLICY.get(key, "")


def get_all_policies() -> dict:
    return COURSE_POLICY


def list_uploaded_knowledge_files():
    if not KNOWLEDGE_UPLOAD_DIR.exists():
        return []
    return sorted(
        [
            path
            for path in KNOWLEDGE_UPLOAD_DIR.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_KNOWLEDGE_EXTENSIONS
        ],
        key=lambda path: path.name,
    )


def list_search_ready_files():
    return [path.name for path in list_uploaded_knowledge_files()]


def read_document_text(file_path):
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        return path.read_text(encoding="utf-8", errors="replace")

    if suffix == ".docx":
        try:
            from docx import Document

            document = Document(path)
            return "\n".join(paragraph.text for paragraph in document.paragraphs)
        except Exception as exc:
            return f"DOCX 파일 내용을 읽을 수 없습니다: {exc}"

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            return f"PDF 파일 내용을 읽을 수 없습니다: {exc}"

    return ""


def chunk_text(text, chunk_size=800):
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return []

    sentences = re.split(r"(?<=[.!?。])\s+|\n+", normalized)
    chunks = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if current and len(current) + len(sentence) > chunk_size:
            chunks.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current.strip())
    return chunks


def extract_question_keywords(question):
    tokens = re.findall(r"[가-힣A-Za-z0-9]+", question or "")
    keywords = []
    for token in tokens:
        token = normalize_keyword(token)
        if len(token) < 2 or token in STOPWORDS:
            continue
        keywords.append(token)
    return keywords


def normalize_keyword(token):
    normalized = str(token or "").strip().lower()
    for suffix in TOKEN_SUFFIXES:
        if len(normalized) > len(suffix) + 1 and normalized.endswith(suffix):
            return normalized[: -len(suffix)]
    return normalized


def search_uploaded_knowledge(question, limit=3):
    keywords = extract_question_keywords(question)
    if not keywords:
        return []

    matches = []
    for file_path in list_uploaded_knowledge_files():
        text = read_document_text(file_path)
        for chunk in chunk_text(text):
            lowered = chunk.lower()
            hit_keywords = [keyword for keyword in keywords if keyword in lowered]
            if not hit_keywords:
                continue
            score = len(hit_keywords)
            matches.append(
                {
                    "filename": file_path.name,
                    "score": score,
                    "matched_keywords": hit_keywords,
                    "text": chunk,
                }
            )

    return sorted(matches, key=lambda item: (-item["score"], item["filename"]))[:limit]


def rebuild_search_cache():
    return {"status": "ok", "files": list_search_ready_files()}


class SimpleEmbeddingFunction:
    def __call__(self, input):
        return [simple_embedding(text) for text in input]


def simple_embedding(text, dimensions=64):
    vector = [0.0] * dimensions
    for token in extract_question_keywords(text):
        index = sum(ord(char) for char in token) % dimensions
        vector[index] += 1.0
    length = sum(value * value for value in vector) ** 0.5
    if length:
        vector = [value / length for value in vector]
    return vector


def get_chroma_collection(reset=False):
    try:
        import chromadb
    except Exception:
        return None

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    if reset:
        try:
            client.delete_collection(CHROMA_COLLECTION)
        except Exception:
            pass
    return client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        embedding_function=SimpleEmbeddingFunction(),
    )


def rebuild_chroma_index():
    collection = get_chroma_collection(reset=True)
    if collection is None:
        return rebuild_search_cache()

    documents = []
    metadatas = []
    ids = []
    for file_path in list_uploaded_knowledge_files():
        text = read_document_text(file_path)
        for index, chunk in enumerate(chunk_text(text), start=1):
            documents.append(chunk)
            metadatas.append({"filename": file_path.name, "chunk_index": index})
            ids.append(f"{file_path.name}-{index}")

    if documents:
        collection.add(documents=documents, metadatas=metadatas, ids=ids)
    return {"status": "ok", "files": list_chroma_indexed_files(), "chunks": len(documents)}


def list_chroma_indexed_files():
    collection = get_chroma_collection(reset=False)
    if collection is None:
        return list_search_ready_files()

    try:
        data = collection.get(include=["metadatas"])
    except Exception:
        return []
    return sorted({metadata.get("filename", "") for metadata in data.get("metadatas", []) if metadata.get("filename")})


def search_chroma_knowledge(question, limit=3):
    collection = get_chroma_collection(reset=False)
    if collection is None:
        return []

    try:
        result = collection.query(query_texts=[question], n_results=limit)
    except Exception:
        return []

    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0] if result.get("distances") else []
    matches = []
    keywords = extract_question_keywords(question)
    for index, document in enumerate(documents):
        metadata = metadatas[index] if index < len(metadatas) else {}
        distance = distances[index] if index < len(distances) else 0
        hit_keywords = [keyword for keyword in keywords if keyword in str(document).lower()]
        if not hit_keywords:
            continue
        matches.append(
            {
                "filename": metadata.get("filename", ""),
                "score": round(1 / (1 + float(distance or 0)), 4),
                "matched_keywords": hit_keywords,
                "text": document,
            }
        )
    return matches
