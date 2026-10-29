def create_chunks(text: str, page_number: int) -> list[dict]:
    """Create focused, sentence-aware chunks from one PDF page."""

    paragraphs = [
        " ".join(paragraph.split())
        for paragraph in re.split(r"\n\s*\n", text)
        if paragraph.strip()
    ]

    # Split paragraphs into sentences while keeping punctuation.
    sentences = []

    for paragraph in paragraphs:
        parts = re.split(r"(?<=[.!?])\s+", paragraph.strip())
        sentences.extend(part.strip() for part in parts if part.strip())

    chunks = []
    current_sentences = []
    current_length = 0

    for sentence in sentences:
        # A very long sentence must be split to respect the chunk limit.
        if len(sentence) > CHUNK_SIZE:
            if current_sentences:
                chunks.append({
                    "page": page_number,
                    "text": " ".join(current_sentences),
                })
                current_sentences = []
                current_length = 0

            for start in range(0, len(sentence), CHUNK_SIZE - CHUNK_OVERLAP):
                piece = sentence[start:start + CHUNK_SIZE].strip()
                if piece:
                    chunks.append({
                        "page": page_number,
                        "text": piece,
                    })
            continue

        extra_length = len(sentence) + (1 if current_sentences else 0)

        if current_length + extra_length > CHUNK_SIZE and current_sentences:
            chunks.append({
                "page": page_number,
                "text": " ".join(current_sentences),
            })

            # Retain a small sentence-level overlap for context.
            overlap_sentences = []
            overlap_length = 0

            for previous in reversed(current_sentences):
                if overlap_length + len(previous) > CHUNK_OVERLAP:
                    break
                overlap_sentences.insert(0, previous)
                overlap_length += len(previous)

            current_sentences = overlap_sentences
            current_length = sum(len(item) for item in current_sentences)

        current_sentences.append(sentence)
        current_length += len(sentence)

    if current_sentences:
        chunks.append({
            "page": page_number,
            "text": " ".join(current_sentences),
        })

    return chunks