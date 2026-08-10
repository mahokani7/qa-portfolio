"""[고도화 1] 검색 품질 지표(Context Precision/Recall) 테스트."""

from quality.retrieval_metrics import context_recall, context_precision, evaluate_retrieval


def test_context_recall_full():
    assert context_recall([1, 0, 0], 1) == 1.0


def test_context_recall_partial():
    assert context_recall([1, 0, 0], 2) == 0.5


def test_context_recall_zero_total():
    assert context_recall([1, 1], 0) == 0.0


def test_context_precision_rank1_is_best():
    # 관련 문서가 1순위 → precision 1.0
    assert context_precision([1, 0, 0]) == 1.0


def test_context_precision_low_when_ranked_last():
    # 관련 문서가 3순위 → precision 1/3
    assert round(context_precision([0, 0, 1]), 2) == 0.33


def test_context_precision_no_relevant():
    assert context_precision([0, 0, 0]) == 0.0


def test_evaluate_retrieval_returns_averages():
    result = evaluate_retrieval()
    assert "avg_recall" in result and "avg_precision" in result
    assert 0.0 <= result["avg_recall"] <= 1.0
    assert 0.0 <= result["avg_precision"] <= 1.0
    assert len(result["cases"]) > 0
