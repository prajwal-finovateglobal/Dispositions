import React, { useState } from 'react'
import { FaExclamationTriangle } from 'react-icons/fa'
import './App.css'
import TranscriptForm from './components/TranscriptForm'
import ResultsDisplay from './components/ResultsDisplay'

function App() {
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (transcript) => {
    setLoading(true)
    setError(null)
    setResults(null)

    try {
      const response = await fetch('http://localhost:8000/disposition', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(transcript),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to classify disposition')
      }

      const data = await response.json()
      setResults(data)
    } catch (err) {
      setError(err.message || 'An error occurred while processing the request')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <div className="container">
        <header className="header">
          <h1>Disposition Classifier</h1>
          <p>Classify loan collection call transcripts with AI</p>
        </header>

        <TranscriptForm onSubmit={handleSubmit} loading={loading} />

        {error && (
          <div className="error-message">
            <span className="error-icon"><FaExclamationTriangle /></span>
            <span><strong>Error:</strong> {error}</span>
          </div>
        )}

        {results && <ResultsDisplay results={results} />}
      </div>
    </div>
  )
}

export default App

