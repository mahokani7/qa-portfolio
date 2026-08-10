"""
ChromaDB 연동 함수(add_file_to_chroma, retrieve_context 등) 테스트.
- OpenAI 임베딩 대신 chromadb 내장 로컬 임베딩(DefaultEmbeddingFunction, onnxruntime 기반)을 사용해
  네트워크/과금 없이(최초 1회 모델 캐시 다운로드 제외) 실제 벡터 검색 흐름을 검증합니다.
"""

import chromadb
from chromadb.utils import embedding_functions

from app.knowledge_base import add_file_to_chroma, retrieve_context


def _local_collection(name: str):
    client = chromadb.EphemeralClient()
    ef = embedding_functions.DefaultEmbeddingFunction()
    return client.get_or_create_collection(name=name, embedding_function=ef)


def test_add_file_to_chroma_returns_chunk_count(tmp_path):
    sample = tmp_path / "sample.txt"
    sample.write_text("교육과정은 총 320시간입니다.\n지각 3회 누적 시 결석 1일로 처리됩니다.", encoding="utf-8")

    collection = _local_collection("test_add_file")
    n_chunks = add_file_to_chroma(sample, collection=collection)

    assert n_chunks > 0
    assert collection.count() == n_chunks


def test_retrieve_context_returns_relevant_chunk(tmp_path):
    sample = tmp_path / "sample2.txt"
    sample.write_text("교육과정은 총 320시간입니다.\n지각 3회 누적 시 결석 1일로 처리됩니다.", encoding="utf-8")

    collection = _local_collection("test_retrieve")
    add_file_to_chroma(sample, collection=collection)

    results = retrieve_context("교육 시간이 몇 시간인가요?", top_k=1, collection=collection)
    assert isinstance(results, list)
    assert len(results) == 1


def test_retrieve_context_on_empty_collection_returns_empty_list():
    collection = _local_collection("test_empty")
    results = retrieve_context("아무 질문", collection=collection)
    assert results == []


def test_add_file_to_chroma_reupload_replaces_previous_chunks(tmp_path):
    sample = tmp_path / "sample3.txt"
    sample.write_text("첫 번째 버전 내용입니다.", encoding="utf-8")

    collection = _local_collection("test_reupload")
    first_count = add_file_to_chroma(sample, collection=collection)

    sample.write_text("완전히 다른 두 번째 버전 내용입니다.", encoding="utf-8")
    second_count = add_file_to_chroma(sample, collection=collection)

    assert collection.count() == second_count
    assert first_count > 0 and second_count > 0
