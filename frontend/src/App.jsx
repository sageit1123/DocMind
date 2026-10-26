
import { useState } from 'react'
import './App.css'

function App() {
  const [message, setMessage] = useState('')
  const [reply, setReply] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedFile, setSelectedFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState('')
  const [uploadError, setUploadError] = useState('')
  const [question, setQuestion] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searchError, setSearchError] = useState("");
  const [isSearching, setIsSearching] = useState(false);

  async function sendMessage(event) {
    event.preventDefault()

    if (!message.trim()) {
      setError('Please write a message. Message cannot be empty.')
      setReply('')
      return
    }

    setLoading(true)
    setError('')
    setReply('')

    try {
      const response = await fetch('http://localhost:8000/api/message', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Something went wrong.')
      }

      setReply(data.reply)
      setMessage('')
    } catch (err) {
      setError(err.message || 'Could not get a response from the backend.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }


  async function uploadDocument() {
    if (!selectedFile) {
      setUploadError('Please select a PDF first.')
      setUploadMessage('')
      return
    }

    setUploading(true)
    setUploadError('')
    setUploadMessage('')

    try {
      const formData = new FormData()
      formData.append('file', selectedFile)

      const response = await fetch('http://localhost:8000/api/upload', {
        method: 'POST',
        body: formData,
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Upload failed.')
      }

      setUploadMessage(`Uploaded successfully: ${data.filename}`)
    } catch (err) {
      setUploadError(err.message || 'Could not upload the file.')
      console.error(err)
    } finally {
      setUploading(false)
    }
  }

  async function searchDocument(event) {
    event.preventDefault();

    const trimmedQuestion = question.trim();

    if (!trimmedQuestion) {
      setSearchError("Please enter a question.");
      setSearchResults([]);
      return;
    }

    setIsSearching(true);
    setSearchError("");
    setSearchResults([]);

    try {
      const response = await fetch("http://127.0.0.1:8000/api/search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: trimmedQuestion,
          top_k: 1,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not search the document.");
      }

      setSearchResults(data.results);
    } catch (error) {
      setSearchError(error.message || "Unable to connect to the backend.");
    } finally {
      setIsSearching(false);
    }
  }


  return (
    <main>
      <h1>DocMind</h1>
      <p className="subtitle">
        Your document intelligence workspace
      </p>

      <section className="message-card">
        <h2>Try a message</h2>
        <p>Send a message to test your connection with the backend.</p>

        <form onSubmit={sendMessage}>
          <input
            type="text"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Type your message..."
            aria-label="Your message"
            maxLength={1000}
          />

          <button type="submit" disabled={loading}>
            {loading ? 'Sending...' : 'Send'}
          </button>
        </form>

        {reply && (
          <p className="reply">
            <strong>Backend reply:</strong> {reply}
          </p>
        )}

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <div className="upload-section">
          <h2>Upload a document</h2>
          <p>Select a PDF to get started.</p>

          <input
            type="file"
            accept=".pdf,application/pdf"
            onChange={(event) =>
              setSelectedFile(event.target.files?.[0] ?? null)
            }
          />

          <button
            type="button"
            onClick={uploadDocument}
            disabled={uploading}
          >
            {uploading ? 'Uploading...' : 'Upload PDF'}
          </button>

          {uploadMessage && (
            <p className="reply" role="status">{uploadMessage}</p>
          )}

          {uploadError && (
            <p className="error" role="alert">{uploadError}</p>
          )}

          {selectedFile && (
            <p>
              Selected file: <strong>{selectedFile.name}</strong>
            </p>
          )}
        </div>

      </section>

      <section className="search-section">
        <h2>Ask your document</h2>
        <p>Ask a question to find relevant passages in your PDF.</p>

        <form onSubmit={searchDocument} className="search-form">
          <input
            type="text"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask a question about your PDF..."
            maxLength={1000}
            disabled={isSearching}
          />

          <button type="submit" disabled={isSearching}>
            {isSearching ? "Searching..." : "Ask"}
          </button>
        </form>

        {searchError && (
          <p className="error-message" role="alert">
            {searchError}
          </p>
        )}

        {searchResults.length > 0 && (
          <div className="search-results">
            <h3>Relevant passages</h3>

            {searchResults.map((result, index) => (
              <article
                className="search-result"
                key={`${result.page}-${index}`}
              >
                <h4>Passage {index + 1} · Page {result.page}</h4>

                <p>{result.text}</p>

                <small>
                  Similarity: {result.similarity}
                </small>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  )
}

export default App
