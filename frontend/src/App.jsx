import { useEffect, useState } from 'react'

function App() {
  const [message, setMessage] = useState('Loading...')

  useEffect(() => {
    fetch('http://localhost:8000/api/message')
      .then((response) => response.json())
      .then((data) => setMessage(data.message))
      .catch(() => setMessage('Could not connect to backend'))
  }, [])

  return (
    <div>
      <h1>DocMind</h1>
      <p>{message}</p>
    </div>
  )
}

export default App