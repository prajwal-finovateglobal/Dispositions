import React, { useState } from 'react'
import { FaFileAlt, FaBullseye } from 'react-icons/fa'
import './TranscriptForm.css'

const TranscriptForm = ({ onSubmit, loading }) => {
  const [transcriptJson, setTranscriptJson] = useState('')
  const [jsonError, setJsonError] = useState(null)

  const handleChange = (e) => {
    const value = e.target.value
    setTranscriptJson(value)
    setJsonError(null)
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    setJsonError(null)

    if (!transcriptJson.trim()) {
      setJsonError('Please paste the transcript JSON')
      return
    }

    try {
      const parsed = JSON.parse(transcriptJson)
      
      // Validate it's an array
      if (!Array.isArray(parsed)) {
        setJsonError('Transcript must be an array of objects')
        return
      }

      // Validate each item has role and content
      const isValid = parsed.every(
        (item) => 
          typeof item === 'object' && 
          item !== null &&
          'role' in item && 
          'content' in item
      )

      if (!isValid) {
        setJsonError('Each item must have "role" and "content" fields')
        return
      }

      onSubmit(parsed)
    } catch (err) {
      setJsonError(`Invalid JSON: ${err.message}`)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="transcript-form">
      <div className="form-section">
        <div className="section-label">
          <span className="label-icon"><FaFileAlt /></span>
          <span className="label-text">Transcript JSON</span>
        </div>
        <div className="section-description">
          Paste your transcript in JSON format: <code>[{`{"role": "user", "content": "..."}`}, ...]</code>
        </div>
        <textarea
          value={transcriptJson}
          onChange={handleChange}
          placeholder='[{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi, how can I help?"}]'
          className="transcript-input"
          rows={12}
          disabled={loading}
        />
        {jsonError && (
          <div className="json-error">{jsonError}</div>
        )}
      </div>

      <button
        type="submit"
        className="submit-btn"
        disabled={loading}
      >
        <span className="btn-icon"><FaBullseye /></span>
        <span>{loading ? 'Classifying...' : 'Classify Disposition'}</span>
      </button>
    </form>
  )
}

export default TranscriptForm

