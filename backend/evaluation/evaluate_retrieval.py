
import json
import time
from pathlib import Path
from statistics import mean

from app.services.retrieval import retrieve_chunks


# Evaluation configuration
BASE_DIR = Path(__file__).resolve().parent
QUESTIONS_FILE = BASE_DIR / "retrieval_questions.json"
REPORT_DIR = BASE_DIR / "reports"

TOP_K = 5

# We retrieve extra chunks because multiple chunks can belong
# to the same document. We evaluate the first 5 unique filenames.
RETRIEVAL_CANDIDATES = 50


def load_questions():
    """Load and validate the evaluation dataset."""

    with open(QUESTIONS_FILE, "r", encoding="utf-8") as file:
        questions = json.load(file)

    if not isinstance(questions, list) or not questions:
        raise ValueError("Evaluation dataset must be a non-empty list.")

    for question in questions:
        if not isinstance(question, dict):
            raise ValueError("Each evaluation entry must be an object.")

        if not question.get("id"):
            raise ValueError("Every question must have an ID.")

        if not question.get("query"):
            raise ValueError(
                f"Question {question.get('id')} has no query."
            )

        expected = question.get("expected_filenames")

        if not isinstance(expected, list) or not expected:
            raise ValueError(
                f"Question {question['id']} has no expected filenames."
            )

    return questions


def get_unique_filenames(passages, limit):
    """Return unique filenames while preserving retrieval order."""

    filenames = []
    seen = set()

    for passage in passages:
        filename = passage.get("filename")

        if not isinstance(filename, str) or not filename:
            continue

        if filename not in seen:
            seen.add(filename)
            filenames.append(filename)

        if len(filenames) == limit:
            break

    return filenames


def calculate_metrics(retrieved, expected):
    """Calculate document-level Precision, Recall and MRR."""

    retrieved_set = set(retrieved)
    expected_set = set(expected)

    relevant_count = len(retrieved_set & expected_set)

    precision = relevant_count / TOP_K
    recall = relevant_count / len(expected_set)

    reciprocal_rank = 0.0

    for rank, filename in enumerate(retrieved, start=1):
        if filename in expected_set:
            reciprocal_rank = 1.0 / rank
            break

    return {
        "precision_at_5": round(precision, 4),
        "recall_at_5": round(recall, 4),
        "reciprocal_rank": round(reciprocal_rank, 4),
    }


def evaluate_question(question):
    """Run retrieval and evaluate one question."""

    query = question["query"]
    expected = question["expected_filenames"]

    start_time = time.perf_counter()

    passages = retrieve_chunks(
        query=query,
        top_k=RETRIEVAL_CANDIDATES,
    )

    latency_ms = (time.perf_counter() - start_time) * 1000

    retrieved = get_unique_filenames(
        passages,
        limit=TOP_K,
    )

    metrics = calculate_metrics(retrieved, expected)

    return {
        "id": question["id"],
        "query": query,
        "expected_filenames": expected,
        "retrieved_filenames": retrieved,
        "metrics": metrics,
        "latency_ms": round(latency_ms, 2),
    }


def main():
    """Run the complete retrieval evaluation."""

    questions = load_questions()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    results = []

    print("\nStarting vector retrieval evaluation...\n")

    # Warm up the embedding model before measuring latency.
    print("Warming up retrieval model...")

    retrieve_chunks(
        query=questions[0]["query"],
        top_k=RETRIEVAL_CANDIDATES,
    )

    print("Warm-up complete.\n")

    

    for question in questions:
        result = evaluate_question(question)
        results.append(result)

        print(f"Question: {result['id']}")
        print(f"Query: {result['query']}")
        print(f"Retrieved: {result['retrieved_filenames']}")
        print(f"Precision@5: {result['metrics']['precision_at_5']}")
        print(f"Recall@5: {result['metrics']['recall_at_5']}")
        print(f"MRR: {result['metrics']['reciprocal_rank']}")
        print(f"Latency: {result['latency_ms']} ms")
        print("-" * 60)

    summary = {
        "retrieval_method": "vector_search",
        "top_k": TOP_K,
        "candidate_chunks": RETRIEVAL_CANDIDATES,
        "total_questions": len(results),
        "average_precision_at_5": round(
            mean(r["metrics"]["precision_at_5"] for r in results), 4
        ),
        "average_recall_at_5": round(
            mean(r["metrics"]["recall_at_5"] for r in results), 4
        ),
        "mean_reciprocal_rank": round(
            mean(r["metrics"]["reciprocal_rank"] for r in results), 4
        ),
        "average_latency_ms": round(
            mean(r["latency_ms"] for r in results), 2
        ),
    }

    report = {
        "summary": summary,
        "results": results,
    }

    report_path = REPORT_DIR / "vector_baseline.json"

    with open(report_path, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4, ensure_ascii=False)

    print("\n========== EVALUATION SUMMARY ==========")

    for metric, value in summary.items():
        print(f"{metric}: {value}")

    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
