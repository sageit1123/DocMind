
import { useEffect, useRef, useState } from "react";
import "./App.css";

const API_BASE_URL = "http://127.0.0.1:8000";

function App() {
  // -----------------------------
  // Chat state
  // -----------------------------
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [conversationId, setConversationId] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [chatError, setChatError] = useState("");

  const abortControllerRef = useRef(null);
  const messagesEndRef = useRef(null);

  // -----------------------------
  // Upload state
  // -----------------------------
  const [selectedFile, setSelectedFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");
  const [uploadError, setUploadError] = useState("");

  // -----------------------------
  // Retrieval playground state
  // -----------------------------
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState("");

  // Keep the newest chat message visible.
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // -----------------------------
  // SSE event parser
  // -----------------------------
  function processSSEBlock(block, onEvent) {
    const dataLines = block
      .split(/\r?\n/)
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart());

    if (dataLines.length === 0) {
      return;
    }

    const data = dataLines.join("\n");

    try {
      onEvent(JSON.parse(data));
    } catch {
      throw new Error("The server returned an invalid streaming event.");
    }
  }

  // -----------------------------
  // Send a question to the RAG API
  // -----------------------------
  async function sendQuestion(event) {
    event.preventDefault();

    const trimmedQuestion = question.trim();

    if (!trimmedQuestion || isStreaming) {
      return;
    }

    setChatError("");
    setQuestion("");
    setIsStreaming(true);

    // Add the user question and an empty assistant message.
    // Incoming tokens will be appended to this assistant message.
    setMessages((previous) => [
      ...previous,
      {
        id: crypto.randomUUID(),
        role: "user",
        content: trimmedQuestion,
      },
      {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "",
        citations: [],
        sources: [],
        streaming: true,
      },
    ]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await fetch(`${API_BASE_URL}/api/ask/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: trimmedQuestion,
          top_k: 5,
          conversation_id: conversationId,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        let errorMessage = "Failed to send your question.";

        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch {
          // Keep the fallback error message.
        }

        throw new Error(errorMessage);
      }

      if (!response.body) {
        throw new Error("Your browser does not support response streaming.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let receivedCompleteEvent = false;

      // Process an individual event from the backend.
      function handleEvent(data) {
        if (data.type === "token") {
          if (typeof data.content !== "string") {
            throw new Error("The server returned an invalid token.");
          }

          setMessages((previous) => {
            const updated = [...previous];
            const lastIndex = updated.length - 1;

            if (
              lastIndex >= 0 &&
              updated[lastIndex].role === "assistant"
            ) {
              updated[lastIndex] = {
                ...updated[lastIndex],
                content: updated[lastIndex].content + data.content,
              };
            }

            return updated;
          });
        } else if (data.type === "complete") {
          receivedCompleteEvent = true;

          if (data.conversation_id != null) {
            setConversationId(data.conversation_id);
          }

          setMessages((previous) => {
            const updated = [...previous];
            const lastIndex = updated.length - 1;

            if (
              lastIndex >= 0 &&
              updated[lastIndex].role === "assistant"
            ) {
              updated[lastIndex] = {
                ...updated[lastIndex],
                content: data.answer || "",
                citations: Array.isArray(data.citations)
                  ? data.citations
                  : [],
                sources: Array.isArray(data.sources) ? data.sources : [],
                streaming: false,
              };
            }

            return updated;
          });
        } else if (data.type === "error") {
          throw new Error(data.message || "The server could not complete the answer.");
        }
      }

      // Read the response incrementally.
      while (true) {
        const { value, done } = await reader.read();

        if (done) {
          buffer += decoder.decode();
        } else {
          buffer += decoder.decode(value, { stream: true });
        }

        // An empty line separates SSE events.
        const blocks = buffer.split(/\r?\n\r?\n/);
        buffer = blocks.pop() || "";

        for (const block of blocks) {
          if (block.trim()) {
            processSSEBlock(block, handleEvent);
          }
        }

        if (done) {
          break;
        }
      }

      // Process a final event if the stream ended without a trailing blank line.
      if (buffer.trim()) {
        processSSEBlock(buffer, handleEvent);
      }

      if (!receivedCompleteEvent) {
        throw new Error("The response stream ended before completion.");
      }
    } catch (error) {
      if (error.name === "AbortError") {
        setChatError("The response was cancelled.");
      } else {
        setChatError(error.message || "Something went wrong while generating the answer.");
      }

      // Mark the current assistant message as no longer streaming.
      setMessages((previous) => {
        const updated = [...previous];
        const lastIndex = updated.length - 1;

        if (
          lastIndex >= 0 &&
          updated[lastIndex].role === "assistant"
        ) {
          updated[lastIndex] = {
            ...updated[lastIndex],
            streaming: false,
          };
        }

        return updated;
      });
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }

  // -----------------------------
  // Start a new conversation
  // -----------------------------
  function startNewChat() {
    if (isStreaming) {
      abortControllerRef.current?.abort();
    }

    setMessages([]);
    setConversationId(null);
    setQuestion("");
    setChatError("");
    setIsStreaming(false);
  }

  // -----------------------------
  // Upload a PDF
  // -----------------------------
  async function uploadDocument(event) {
    event.preventDefault();

    if (!selectedFile || isUploading) {
      return;
    }

    if (selectedFile.type !== "application/pdf") {
      setUploadError("Please select a PDF file.");
      return;
    }

    setUploadError("");
    setUploadMessage("");
    setIsUploading(true);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const response = await fetch(`${API_BASE_URL}/api/upload`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "PDF upload failed.");
      }

      setUploadMessage(
        data.message ||
          `Upload successful. Document ID: ${data.document_id ?? "created"}.`
      );
      setSelectedFile(null);

      // Clear the native file input.
      const fileInput = document.getElementById("pdf-file");
      if (fileInput) {
        fileInput.value = "";
      }
    } catch (error) {
      setUploadError(error.message || "Unable to upload the PDF.");
    } finally {
      setIsUploading(false);
    }
  }

  // -----------------------------
  // Search retrieved passages
  // -----------------------------
  async function searchDocuments(event) {
    event.preventDefault();

    const trimmedQuery = searchQuery.trim();

    if (!trimmedQuery || isSearching) {
      return;
    }

    setIsSearching(true);
    setSearchError("");
    setSearchResults([]);

    try {
      const response = await fetch(`${API_BASE_URL}/api/search`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: trimmedQuery,
          top_k: 5,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Search request failed.");
      }

      setSearchResults(Array.isArray(data.results) ? data.results : []);
    } catch (error) {
      setSearchError(error.message || "Unable to search documents.");
    } finally {
      setIsSearching(false);
    }
  }

  // -----------------------------
  // Render citation information
  // -----------------------------
  function renderCitations(message) {
    const citations =
      message.citations?.length > 0
        ? message.citations
        : message.sources || [];

    if (citations.length === 0) {
      return null;
    }

    return (
      <div className="citation-panel">
        <div className="citation-heading">
          <span className="citation-icon">↗</span>
          Sources
        </div>

        <div className="citation-list">
          {citations.map((citation, index) => (
            <div
              className="citation-item"
              key={`${citation.chunk_id ?? citation.document_id ?? "source"}-${index}`}
            >
              <div className="citation-file">
                {citation.filename || `Source ${index + 1}`}
              </div>

              <div className="citation-meta">
                {citation.page != null
                  ? `Page ${citation.page}`
                  : "Page information unavailable"}
                {citation.number != null
                  ? ` · Citation [${citation.number}]`
                  : ""}
              </div>

              {citation.text && (
                <p className="citation-excerpt">{citation.text}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">D</div>
          <span>DocMind</span>
          <span className="brand-version">RAG Workspace</span>
        </div>

        <div className="topbar-right">
          <span className="connection-indicator">
            <span className="status-dot" />
            Local workspace
          </span>
          <button className="new-chat-button" onClick={startNewChat}>
            + New chat
          </button>
        </div>
      </header>

      <main className="workspace">
        <section className="page-heading">
          <div>
            <p className="eyebrow">YOUR DOCUMENT KNOWLEDGE BASE</p>
            <h1>Ask your documents.</h1>
            <p className="page-subtitle">
              Upload PDFs, retrieve relevant passages, and get answers
              grounded in your documents.
            </p>
          </div>
        </section>

        <div className="workspace-grid">
          {/* Main chat area */}
          <section className="chat-card">
            <div className="section-header">
              <div>
                <p className="section-kicker">AI ASSISTANT</p>
                <h2>Document chat</h2>
                <p className="section-description">
                  Ask questions and receive answers with source citations.
                </p>
              </div>

              <span className="model-label">RAG · Streaming</span>
            </div>

            <div className="chat-messages">
              {messages.length === 0 ? (
                <div className="chat-empty">
                  <div className="empty-icon">✳</div>
                  <h3>What would you like to know?</h3>
                  <p>
                    Ask a question about your uploaded documents. DocMind
                    will retrieve relevant passages before generating an answer.
                  </p>

                  <div className="suggestion-list">
                    <button
                      type="button"
                      onClick={() =>
                        setQuestion("Summarize the main points in my documents.")
                      }
                    >
                      Summarize my documents
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        setQuestion("What are the important requirements?")
                      }
                    >
                      Find important requirements
                    </button>
                  </div>
                </div>
              ) : (
                messages.map((message) => (
                  <article
                    className={`chat-message ${message.role}`}
                    key={message.id}
                  >
                    <div className="message-avatar">
                      {message.role === "user" ? "Y" : "D"}
                    </div>

                    <div className="message-body">
                      <div className="message-author">
                        {message.role === "user" ? "You" : "DocMind"}
                      </div>

                      <div className="message-content">
                        {message.content || (
                          <span className="thinking-label">
                            Retrieving passages and generating an answer
                            <span className="typing-dots">...</span>
                          </span>
                        )}
                        {message.streaming && message.content && (
                          <span className="streaming-cursor" />
                        )}
                      </div>

                      {message.role === "assistant" &&
                        !message.streaming &&
                        renderCitations(message)}
                    </div>
                  </article>
                ))
              )}

              <div ref={messagesEndRef} />
            </div>

            {chatError && (
              <div className="error-message" role="alert">
                {chatError}
              </div>
            )}

            <form className="chat-composer" onSubmit={sendQuestion}>
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Ask a question about your documents..."
                rows={2}
                disabled={isStreaming}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    if (!isStreaming) {
                      event.currentTarget.form.requestSubmit();
                    }
                  }
                }}
              />

              <div className="composer-footer">
                <span>Answers are grounded in retrieved document passages.</span>
                <button
                  type="submit"
                  disabled={!question.trim() || isStreaming}
                >
                  {isStreaming ? "Generating..." : "Send question"}
                  <span aria-hidden="true"> ↗</span>
                </button>
              </div>
            </form>
          </section>

          {/* Right-hand document panel */}
          <aside className="side-panel">
            <section className="side-card upload-card">
              <div className="side-card-heading">
                <div className="side-icon">↑</div>
                <div>
                  <h2>Knowledge base</h2>
                  <p>Add documents to your workspace</p>
                </div>
              </div>

              <form onSubmit={uploadDocument} className="upload-form">
                <label className="file-dropzone" htmlFor="pdf-file">
                  <span className="upload-symbol">＋</span>
                  <strong>
                    {selectedFile ? selectedFile.name : "Choose a PDF file"}
                  </strong>
                  <span>PDF documents only</span>
                  <input
                    id="pdf-file"
                    type="file"
                    accept="application/pdf,.pdf"
                    onChange={(event) =>
                      setSelectedFile(event.target.files?.[0] || null)
                    }
                  />
                </label>

                <button
                  className="upload-button"
                  type="submit"
                  disabled={!selectedFile || isUploading}
                >
                  {isUploading ? "Uploading..." : "Upload document"}
                </button>
              </form>

              {uploadMessage && (
                <div className="success-message" role="status">
                  {uploadMessage}
                </div>
              )}

              {uploadError && (
                <div className="error-message" role="alert">
                  {uploadError}
                </div>
              )}

              <p className="upload-note">
                Documents are processed asynchronously. Wait for ingestion
                to finish before asking questions about a newly uploaded PDF.
              </p>
            </section>

            <section className="side-card search-card">
              <div className="side-card-heading">
                <div className="side-icon search-icon">⌕</div>
                <div>
                  <h2>Retrieval playground</h2>
                  <p>Inspect the passages returned by vector search</p>
                </div>
              </div>

              <form className="playground-form" onSubmit={searchDocuments}>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Enter a search query..."
                  disabled={isSearching}
                />
                <button type="submit" disabled={!searchQuery.trim() || isSearching}>
                  {isSearching ? "Searching..." : "Search"}
                </button>
              </form>

              {searchError && (
                <div className="error-message" role="alert">
                  {searchError}
                </div>
              )}

              {searchResults.length > 0 && (
                <div className="playground-results">
                  <div className="results-heading">
                    Retrieved passages
                    <span>{searchResults.length}</span>
                  </div>

                  {searchResults.map((result, index) => (
                    <article
                      className="playground-result"
                      key={result.chunk_id ?? index}
                    >
                      <div className="result-meta">
                        <strong>{result.filename || "Document"}</strong>
                        <span>
                          {result.page != null
                            ? `Page ${result.page}`
                            : "Page unavailable"}
                        </span>
                      </div>

                      <p>{result.text}</p>

                      {typeof result.similarity === "number" && (
                        <div className="similarity-row">
                          <span>Cosine similarity</span>
                          <strong>
                            {(result.similarity * 100).toFixed(1)}%
                          </strong>
                        </div>
                      )}
                    </article>
                  ))}
                </div>
              )}

              {searchResults.length === 0 &&
                !isSearching &&
                !searchError && (
                  <p className="playground-note">
                    Search results will appear here.
                  </p>
                )}
            </section>
          </aside>
        </div>

        <footer className="app-footer">
          <span>DocMind · Document-grounded question answering</span>
          <span>Week 4 · Streaming RAG</span>
        </footer>
      </main>
    </div>
  );
}

export default App;
