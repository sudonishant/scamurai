"""Regression coverage for Unicode text handling and diagnostic semantics."""
from types import SimpleNamespace

from app.services.analytics import _cosine, _tfidf_vectors, _tokens
from app.services.textutil import normalize_text
from scripts.evaluate_multilingual import evaluate


def test_devanagari_marks_survive_normalization_and_tokenization():
    assert normalize_text("बाढ़, पुल!") == "बाढ़ पुल"
    tokens = _tokens("बाढ़ के कारण उत्तरी पुल और पूर्वी सड़क बंद हैं।")
    assert {"बाढ़", "कारण", "उत्तरी", "पुल", "पूर्वी", "सड़क", "बंद"}.issubset(tokens)

    texts = [
        "बाढ़ के कारण उत्तरी पुल और पूर्वी सड़क बंद हैं।",
        "उत्तरी पुल तथा पूर्वी सड़क बाढ़ के कारण बंद हैं।",
    ]
    posts = [SimpleNamespace(raw_text=text, normalized_text=normalize_text(text)) for text in texts]
    vectors, token_sets = _tfidf_vectors(posts)
    assert all(token_sets)
    assert _cosine(vectors[0], vectors[1]) >= 0.48


def test_multilingual_report_is_diagnostic_not_semantic_or_accuracy_claim():
    report = evaluate()
    assert report["synthetic_diagnostic"] is True
    assert report["method"]["semantic_embedding_model"] == "not_configured"
    assert report["method"]["cross_lingual_semantic_score"] == "unavailable_not_zero"
    assert report["summary"]["pairs"] == len(report["pairs"])
    assert report["summary"]["empty_token_pairs"] == 0
    confusion_sum = sum(report["summary"][key] for key in (
        "true_positive", "false_positive", "true_negative", "false_negative"))
    assert confusion_sum == len(report["pairs"])
    # The fixture deliberately retains hard limitations rather than hiding them.
    assert report["by_track"]["cross_lingual_semantic_equivalence"]["false_negative"] > 0
    assert report["by_track"]["different_narrative_controls"]["false_positive"] > 0
