
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services.retrieval import retrieve_chunks


@patch("app.services.retrieval.get_connection")
@patch("app.services.retrieval.embedding_model")
def test_retrieve_chunks_returns_formatted_results(
    mock_embedding_model,
    mock_get_connection,
):
    # Arrange: mock query embedding.
    mock_embedding_model.encode.return_value = np.array([0.1, 0.2, 0.3])

    # Arrange: mock database result.
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        (
            12,
            3,
            4,
            "Students can request refunds within 15 days.",
            "campus_policy.pdf",
            0.82314,
        )
    ]

    mock_connection = MagicMock()
    mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_connection.return_value.__enter__.return_value = mock_connection

    # Act.
    results = retrieve_chunks("What is the refund policy?", top_k=5)

    # Assert.
    assert len(results) == 1

    assert results[0] == {
        "chunk_id": 12,
        "document_id": 3,
        "page": 4,
        "filename": "campus_policy.pdf",
        "text": "Students can request refunds within 15 days.",
        "similarity": 0.8231,
    }

    mock_embedding_model.encode.assert_called_once()
    mock_get_connection.assert_called_once()
    mock_cursor.execute.assert_called_once()


@patch("app.services.retrieval.get_connection")
@patch("app.services.retrieval.embedding_model")
def test_retrieve_chunks_returns_empty_list(
    mock_embedding_model,
    mock_get_connection,
):
    mock_embedding_model.encode.return_value = np.array([0.1, 0.2, 0.3])

    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []

    mock_connection = MagicMock()
    mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_connection.return_value.__enter__.return_value = mock_connection

    results = retrieve_chunks("A question with no matching chunks")

    assert results == []


@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
def test_retrieve_chunks_rejects_empty_query(query):
    with pytest.raises(ValueError, match="Query cannot be empty"):
        retrieve_chunks(query)


@pytest.mark.parametrize("top_k", [0, -1, 11, 1.5, "5", True])
def test_retrieve_chunks_rejects_invalid_top_k(top_k):
    with pytest.raises(ValueError):
        retrieve_chunks("refund policy", top_k=top_k)


@patch("app.services.retrieval.get_connection")
@patch("app.services.retrieval.embedding_model")
def test_retrieve_chunks_database_error_propagates(
    mock_embedding_model,
    mock_get_connection,
):
    mock_embedding_model.encode.return_value = np.array([0.1, 0.2, 0.3])

    mock_get_connection.side_effect = RuntimeError("Database unavailable")

    with pytest.raises(RuntimeError, match="Database unavailable"):
        retrieve_chunks("refund policy")
