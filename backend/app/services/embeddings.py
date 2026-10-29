
from sentence_transformers import SentenceTransformer

# Load the embedding model once and reuse it.
embedding_model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2"
)
