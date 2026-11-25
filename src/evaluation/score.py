"""Stage 2: score an answers file (ROUGE, semantic similarity, NLI entailment).

Independent of the chatbot: it only reads the answers file written by generate.py, so you can
change the metrics here and re-score old answers at any time.

    python -m src.evaluation.score --answers data/eval_results/answers_1.4.0.jsonl [--scorer stub]

Writes <answers>_scores.csv (one row per case) and <answers>_summary.json (means).
"""
import argparse
import json
import re
from pathlib import Path

import pandas as pd

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
NLI_MODEL = "cross-encoder/nli-deberta-v3-base"

METRIC_COLUMNS = [
    "rouge1_f1", "rouge2_f1", "rougeL_f1",
    "cosine",
    "nli_entailment", "nli_contradiction", "nli_neutral",
    "numeric_recall",
]


def numeric_recall(gold: str, answer: str) -> float | None:
    """Share of the numbers in the gold that also appear in the answer (ROUGE/cosine/NLI can miss
    a wrong number). None if the gold has no numbers. Delete this column if you don't want it."""
    def numbers(text):
        return {m.replace(",", "") for m in re.findall(r"\d+(?:[.,]\d+)*%?", text)}
    gold_numbers = numbers(gold)
    return len(gold_numbers & numbers(answer)) / len(gold_numbers) if gold_numbers else None


class Scorer:
    def __init__(self):
        from rouge_score import rouge_scorer
        self._rouge = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)

    def cosine(self, a: str, b: str) -> float:
        raise NotImplementedError

    def nli(self, premise: str, hypothesis: str) -> dict[str, float]:
        """-> {'entailment': p, 'contradiction': p, 'neutral': p}"""
        raise NotImplementedError

    def score(self, gold: str, answer: str) -> dict[str, float | None]:
        rouge = self._rouge.score(gold, answer)
        nli = self.nli(gold, answer)  # premise = gold answer, hypothesis = chatbot answer
        return {
            "rouge1_f1": rouge["rouge1"].fmeasure,
            "rouge2_f1": rouge["rouge2"].fmeasure,
            "rougeL_f1": rouge["rougeL"].fmeasure,
            "cosine": self.cosine(gold, answer),
            "nli_entailment": nli.get("entailment", 0.0),
            "nli_contradiction": nli.get("contradiction", 0.0),
            "nli_neutral": nli.get("neutral", 0.0),
            "numeric_recall": numeric_recall(gold, answer),
        }


class ModelScorer(Scorer):
    """Same models as the notebook."""

    def __init__(self, device: str | None = None):
        super().__init__()
        import torch
        from sentence_transformers import SentenceTransformer
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        self._torch = torch
        self._device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._embedder = SentenceTransformer(EMBEDDING_MODEL, device=self._device)
        self._tokenizer = AutoTokenizer.from_pretrained(NLI_MODEL)
        self._nli = AutoModelForSequenceClassification.from_pretrained(NLI_MODEL).to(self._device).eval()
        self._labels = {int(i): self._canonical(l) for i, l in self._nli.config.id2label.items()}

    @staticmethod
    def _canonical(label: str) -> str:
        label = str(label).lower()
        for key, name in (("entail", "entailment"), ("contrad", "contradiction"), ("neutral", "neutral")):
            if key in label:
                return name
        return label

    def cosine(self, a: str, b: str) -> float:
        embeddings = self._embedder.encode([a, b], convert_to_tensor=True, normalize_embeddings=True)
        return float(self._torch.matmul(embeddings[0], embeddings[1]))

    def nli(self, premise: str, hypothesis: str) -> dict[str, float]:
        encoded = self._tokenizer(premise, hypothesis, return_tensors="pt", truncation=True,
                                  max_length=512).to(self._device)
        with self._torch.no_grad():
            probs = self._torch.softmax(self._nli(**encoded).logits, dim=-1)[0].tolist()
        return {self._labels[i]: p for i, p in enumerate(probs)}


class StubScorer(Scorer):
    """Token-overlap stand-ins for cosine/NLI. ONLY for smoke-testing the pipeline offline."""

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(re.findall(r"\w+", text.lower()))

    def cosine(self, a: str, b: str) -> float:
        ta, tb = self._tokens(a), self._tokens(b)
        return len(ta & tb) / max(len(ta | tb), 1)

    def nli(self, premise: str, hypothesis: str) -> dict[str, float]:
        th = self._tokens(hypothesis)
        entailment = len(th & self._tokens(premise)) / max(len(th), 1)
        return {"entailment": entailment, "contradiction": 0.0, "neutral": 1 - entailment}


def score_file(answers_path: Path, *, scorer: str = "models", out_path: Path | None = None) -> pd.DataFrame:
    answers_path = Path(answers_path)
    records = [json.loads(l) for l in answers_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not records:
        raise ValueError(f"No answers in {answers_path}")
    engine = StubScorer() if scorer == "stub" else ModelScorer()

    rows = []
    for record in records:
        metrics = engine.score(record["gold_answer"], record["answer"])
        rows.append({**record, **metrics})
        print(f"{record['case_id']}  entailment={metrics['nli_entailment']:.2f}  "
              f"cosine={metrics['cosine']:.2f}  rougeL={metrics['rougeL_f1']:.2f}")
    df = pd.DataFrame(rows)

    out_path = out_path or answers_path.with_name(answers_path.stem + "_scores.csv")
    df.to_csv(out_path, index=False)
    summary = {"n": len(df), **{c: (None if pd.isna(df[c].mean()) else float(df[c].mean()))
                                for c in METRIC_COLUMNS + ["latency_ms"] if c in df}}
    summary_path = out_path.with_name(answers_path.stem + "_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"\nSUMMARY (means) {json.dumps(summary, indent=2)}\nScores -> {out_path}")
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--scorer", choices=["models", "stub"], default="models")
    args = parser.parse_args()
    score_file(args.answers, scorer=args.scorer, out_path=args.out)
