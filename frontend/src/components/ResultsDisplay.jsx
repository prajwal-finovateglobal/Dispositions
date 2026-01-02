import React from 'react'
import './ResultsDisplay.css'

const ResultsDisplay = ({ results }) => {
  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.8) return '#00d4ff'
    if (confidence >= 0.5) return '#ffc107'
    if (confidence >= 0) return '#ff6b6b'
    return '#6c757d'
  }

  const getConfidenceLabel = (confidence) => {
    if (confidence >= 0.8) return 'High'
    if (confidence >= 0.5) return 'Medium'
    if (confidence >= 0) return 'Low'
    return 'N/A'
  }

  return (
    <div className="results-display">
      <h2 className="results-title">Classification Results</h2>

      <div className="results-grid">
        <div className="result-card primary">
          <div className="card-header">
            <h3>Disposition Code</h3>
          </div>
          <div className="card-content">
            <div className="disposition-code">{results.Disposition_code}</div>
          </div>
        </div>

        <div className="result-card">
          <div className="card-header">
            <h3>Confidence Score</h3>
          </div>
          <div className="card-content">
            <div
              className="confidence-badge"
              style={{ backgroundColor: getConfidenceColor(results.confidence) }}
            >
              <span className="confidence-value">
                {results.confidence >= 0
                  ? (results.confidence * 100).toFixed(1)
                  : 'N/A'}
                %
              </span>
              <span className="confidence-label">
                {getConfidenceLabel(results.confidence)}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="result-section">
        <h3 className="section-title">Explanation</h3>
        <div className="section-content explanation">
          <p>{results.explanation}</p>
        </div>
      </div>

      {results.summary && (
        <div className="result-section">
          <h3 className="section-title">Summary</h3>
          <div className="section-content summary">
            <p>{results.summary}</p>
          </div>
        </div>
      )}

      {results.key_points && results.key_points.length > 0 && (
        <div className="result-section">
          <h3 className="section-title">Key Points</h3>
          <div className="section-content key-points">
            <ul>
              {results.key_points.map((point, index) => (
                <li key={index}>{point}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}

export default ResultsDisplay

