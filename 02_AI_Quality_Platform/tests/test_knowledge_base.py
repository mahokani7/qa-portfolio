"""app.knowledge_base의 순수 로직(청크 분할, 파일 목록, 텍스트 추출)을 검증합니다. API 호출 없음."""

from app.knowledge_base import chunk_text, list_uploaded_knowledge_files, read_document_text


def test_chunk_text_splits_long_text_within_chunk_size():
    text = "가" * 1000
    chunks = chunk_text(text, chunk_size=400, overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 400 for c in chunks)


def test_chunk_text_empty_text_returns_empty_list():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_text_short_text_returns_single_chunk():
    chunks = chunk_text("짧은 문장입니다.", chunk_size=400, overlap=50)
    assert chunks == ["짧은 문장입니다."]


def test_list_uploaded_knowledge_files_includes_known_file():
    files = list_uploaded_knowledge_files()
    names = [f.name for f in files]
    assert "교육과정 개요.txt" in names


def test_read_document_text_txt_file_returns_nonempty_string():
    files = list_uploaded_knowledge_files()
    txt_file = next(f for f in files if f.suffix == ".txt")
    text = read_document_text(txt_file)
    assert isinstance(text, str)
    assert len(text) > 0


def test_read_document_text_rejects_unsupported_extension(tmp_path):
    bad_file = tmp_path / "unsupported.xyz"
    bad_file.write_text("data")
    try:
        read_document_text(bad_file)
        assert False, "예외가 발생해야 함"
    except ValueError:
        pass
