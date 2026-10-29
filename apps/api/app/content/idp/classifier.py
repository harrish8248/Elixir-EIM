"""
Document Classifier for Elixir EIM IDP.
Combines TF-IDF + Logistic Regression (trained strictly on the train split)
with keyword and structural layout heuristics.
"""

import json
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from apps.api.app.content.idp.models import DocumentType
from apps.api.app.platform.logging import logger

DATA_DIR = Path("docs/ocr-benchmark/data")
SPLITS_PATH = Path("docs/ocr-benchmark/splits.json")

KEYWORD_RULES = {
    DocumentType.INVOICE: ["invoice", "bill to", "tax invoice", "balance due", "total amount due", "subtotal", "payment terms"],
    DocumentType.PURCHASE_ORDER: ["purchase order", "p.o. #", "issued by", "order date", "delivery terms", "procurement"],
    DocumentType.RECEIPT: ["receipt", "pos terminal", "card payment", "register #", "cashier", "itemised receipt"],
    DocumentType.CONTRACT: ["agreement", "contract", "confidentiality", "in witness whereof", "parties hereby agree", "governing law"],
    DocumentType.ID_DOCUMENT: ["passport", "driver license", "national id", "identification card", "date of birth", "nationality"],
}


class DocumentClassifier:
    """Classifies document full text into standard categories."""

    def __init__(self):
        self.vectorizer = TfidfVectorizer(max_features=1500, ngram_range=(1, 2), stop_words="english")
        self.classifier = LogisticRegression(max_iter=500, random_state=42, class_weight="balanced")
        self._is_trained = False
        self._classes = [d.value for d in DocumentType]
        self._init_model()

    def _init_model(self):
        """Train classifier strictly on the train split data."""
        if not SPLITS_PATH.exists():
            logger.warning(f"Benchmark splits file not found at {SPLITS_PATH}; relying on heuristic rules.")
            return

        try:
            with open(SPLITS_PATH, encoding="utf-8") as f:
                splits = json.load(f)

            train_ids = splits.get("train", [])
            texts, labels = [], []

            for doc_id in train_ids:
                p = DATA_DIR / f"{doc_id}.json"
                if p.exists():
                    with open(p, encoding="utf-8") as f:
                        data = json.load(f)
                        t = data.get("full_text", "")
                        lbl = data.get("document_type", "other")
                        if t and lbl:
                            texts.append(t)
                            labels.append(lbl)

            if texts and labels:
                X_train = self.vectorizer.fit_transform(texts)
                self.classifier.fit(X_train, labels)
                self._classes = list(self.classifier.classes_)
                self._is_trained = True
                logger.info(f"IDP DocumentClassifier successfully trained on {len(texts)} train-split samples.")
        except Exception as e:
            logger.warning(f"Could not initialize ML document classifier: {e}")

    def classify(self, text: str) -> tuple[DocumentType, float]:
        """Classify document text and return (document_type, confidence)."""
        clean_text = text.lower().strip()
        if not clean_text:
            return DocumentType.OTHER, 0.50

        # Heuristic scoring
        rule_scores: dict[DocumentType, int] = {t: 0 for t in DocumentType}
        for dtype, keywords in KEYWORD_RULES.items():
            for kw in keywords:
                if kw in clean_text:
                    rule_scores[dtype] += 2

        best_rule_type = max(rule_scores, key=rule_scores.get)  # type: ignore[arg-type]
        best_rule_score = rule_scores[best_rule_type]

        # ML prediction
        if self._is_trained:
            try:
                vec = self.vectorizer.transform([text])
                probs = self.classifier.predict_proba(vec)[0]
                best_idx = int(probs.argmax())
                pred_label = self._classes[best_idx]
                ml_conf = float(probs[best_idx])

                # Blend rule with ML
                if best_rule_score >= 4 and pred_label != best_rule_type.value:
                    # High rule confidence override if ML is uncertain
                    if ml_conf < 0.65:
                        return best_rule_type, 0.88
                elif pred_label == best_rule_type.value and best_rule_score >= 2:
                    # Agreement between ML and rules boosts confidence
                    conf = max(ml_conf, min(0.75 + (best_rule_score * 0.06), 0.98))
                    return DocumentType(pred_label), round(conf, 4)

                try:
                    return DocumentType(pred_label), round(ml_conf, 4)
                except ValueError:
                    return DocumentType.OTHER, round(ml_conf, 4)
            except Exception as e:
                logger.warning(f"ML classification inference failed: {e}")

        # Fallback to rule scoring
        if best_rule_score >= 2:
            conf = min(0.70 + (best_rule_score * 0.08), 0.98)
            return best_rule_type, round(conf, 2)

        return DocumentType.OTHER, 0.50

