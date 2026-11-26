"""Stage 2: score an answers file (ROUGE, semantic similarity, NLI entailment).
 
Independent of the chatbot: it only reads the answers file written by generate.py, so you can
change the metrics here and re-score old answers at any time.
 
    python -m src.evaluation.score --answers answers/eval_answers.json [--scorer stub] [--force]
 
The scores are written INTO the answers file itself:
  - every case gets a "scoring" block with its metrics
  - the top-level "summary" holds the mean of each metric over all scored cases
Cases that already have a "scoring" block are skipped unless --force is given.
"""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
 
from src.evaluation.generate import load_answers, save_answers
 
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
    a wrong number). None if the gold has no numbers. Delete this metric if you don't want it."""
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
 
 
def aggregate(cases: list[dict]) -> dict:
    """Mean of every metric over all scored cases (None values, e.g. numeric_recall, are skipped)."""
    scored = [c["scoring"] for c in cases if "scoring" in c]
    metrics = {}
    for name in METRIC_COLUMNS:
        values = [s[name] for s in scored if s.get(name) is not None]
        metrics[name] = sum(values) / len(values) if values else None
    latencies = [c["latency_ms"] for c in cases if c.get("latency_ms") is not None]
    return {
        "n_cases": len(cases),
        "n_scored": len(scored),
        "scored_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "mean_latency_ms": sum(latencies) / len(latencies) if latencies else None,
    }
 
 
def score_file(answers_path: Path, *, scorer: str = "models", force: bool = False) -> dict:
    """Add a 'scoring' block to every unscored case and write the overall summary, in the same file."""
    answers_path = Path(answers_path)
    data = load_answers(answers_path)
    cases = data["cases"]
    if not cases:
        raise ValueError(f"No answers in {answers_path}")
 
    pending = [c for c in cases if force or "scoring" not in c]
    if not pending:
        print(f"All {len(cases)} cases are already scored (use --force to re-score).")
        data["summary"] = aggregate(cases)  # cheap; keeps the summary in sync
        save_answers(answers_path, data)
        return data["summary"]
 
    engine = StubScorer() if scorer == "stub" else ModelScorer()  # models are loaded only if needed
    for case in pending:
        case["scoring"] = engine.score(case["gold_answer"], case["answer"])
        s = case["scoring"]
        print(f"{case.get('scenario')}/{case['case_id']}  entailment={s['nli_entailment']:.2f}  "
              f"cosine={s['cosine']:.2f}  rougeL={s['rougeL_f1']:.2f}")
        save_answers(answers_path, data)  # progress survives a crash
 
    data["summary"] = aggregate(cases)
    save_answers(answers_path, data)
    print(f"\nSUMMARY\n{json.dumps(data['summary'], indent=2)}\nScores written to {answers_path}")
    return data["summary"]
 
 
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--scorer", choices=["models", "stub"], default="models")
    parser.add_argument("--force", action="store_true",
                        help="Re-score cases that already have a scoring block")
    args = parser.parse_args()
    score_file(args.answers, scorer=args.scorer, force=args.force)
 