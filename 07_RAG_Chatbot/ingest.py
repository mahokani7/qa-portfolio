from rag_service import rebuild_vector_db


if __name__ == "__main__":
    result = rebuild_vector_db()

    print(f"읽은 원본 문서 수: {result['original_document_count']}")
    print(f"저장된 문서 조각 수: {result['chunk_count']}")
    print("벡터 DB 생성이 완료되었습니다.")