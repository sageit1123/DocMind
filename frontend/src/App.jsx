
import { useState } from 'react'

function App() {
  const [message, setMessage] = useState('')
  const [reply, setReply] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function sendMessage(event) {
    event.preventDefault()
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

      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`)
      }

      const data = await response.json()
      setReply(data.reply)
    } catch (err) {
      setError('Could not get a response from the backend.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main>
      <h1>DocMind</h1>
      <p>Send a message to your backend.</p>

      <form onSubmit={sendMessage}>
        <input
          type="text"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="Type your message..."
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Sending...' : 'Send'}
        </button>
      </form>

      {reply && <p>Backend reply: {reply}</p>}
      {error && <p role="alert">{error}</p>}
    </main>
  )
}

export default App
