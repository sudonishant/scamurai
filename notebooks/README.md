# Evaluation notebooks (experimental only)

`multilingual_semantic_evaluation.ipynb` is an optional Colab/Jupyter experiment for comparing the production lexical narrative candidate method with a reviewed multilingual Sentence Transformers model.

## Allowed use

- Small synthetic or authorized, non-sensitive labelled text pairs.
- Model-card/license review, pairwise similarity inspection and threshold/calibration experiments.
- Reporting per-language/per-track false positives and false negatives with event/account-separated evaluation data.

## Not supported here

- Production ingestion, always-on collection, scheduled alerts or a public API.
- Permanent or sensitive case storage, PAT/provider credentials, private model tokens or hard-coded secrets.
- Creating synthetic/deepfake content, platform bypasses, or consequential automated decisions.

Colab resources are temporary and not guaranteed; review the [official Colab FAQ](https://research.google.com/colaboratory/faq.html). A shared notebook includes its saved text/code/output, so clear outputs before sharing anything sensitive. This repository notebook is saved without outputs.

The optional model cell uses the official [Sentence Transformers pairwise similarity API](https://www.sbert.net/docs/sentence_transformer/usage/semantic_textual_similarity.html). It does not select or execute a model by default. Set an exact public model ID and preferably a pinned revision only after reviewing its model card, languages, license and intended similarity function. The production lexical threshold `0.48` is **not** transferred to embedding scores.

The notebook and `backend/scripts/evaluate_multilingual.py` are diagnostics, not accuracy certification. No semantic-model result is claimed until the cells are actually run and the resulting report is inspected on representative held-out data.
