
from app.services.keyword_retrieval import retrieve_keyword_chunks


queries = [
    "How can I reset my campus password?",
    "What is the employee leave policy?",
    "What are the specifications of Orbit devices?",
    "How do I report an IT issue?",
]

for query in queries:
    print("\n" + "=" * 80)
    print("QUERY:", query)
    print("=" * 80)

    results = retrieve_keyword_chunks(query, top_k=5)

    if not results:
        print("No matching chunks found.")
        continue

    for rank, result in enumerate(results, start=1):
        print(f"\nRank: {rank}")
        print("Filename:", result["filename"])
        print("Page:", result["page"])
        print("Keyword score:", result["keyword_score"])
        print("Text:", result["text"][:300])
