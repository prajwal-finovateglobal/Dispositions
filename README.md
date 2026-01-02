# Disposition Classifier

A Call Center Disposition Classifier for Loan Collections that uses AI to classify call transcripts and determine the appropriate disposition code.

## Features

- AI-powered classification of call transcripts
- Automatic connection status detection
- Grievance detection and categorization
- Confidence scoring for classifications
- Modern dark-themed React UI
- RESTful API with FastAPI

## Prerequisites

- Python 3.8+
- Node.js 16+ and npm
- OpenAI API key (set in `.env` file)

## Project Structure

```
.
├── frontend/          # React frontend application
├── csv/              # CSV data files for dispositions
├── main.py           # FastAPI application entry point
├── Disposition_classifier_agnet.py  # Main classification logic
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

## Setup Instructions

### Backend Setup

1. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create a `.env` file in the root directory:**
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   OPENAI_MODEL=gpt-4o-mini  # or your preferred model
   ```

4. **Run the backend server:**
   ```bash
   python main.py
   ```
   
   The API will be available at `http://localhost:8000`
   
   You can also access the API documentation at `http://localhost:8000/docs`

### Frontend Setup

1. **Navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start the development server:**
   ```bash
   npm run dev
   ```
   
   The frontend will be available at `http://localhost:3000`

## Usage

1. **Start the backend server** (from the root directory):
   ```bash
   python main.py
   ```

2. **Start the frontend** (from the frontend directory):
   ```bash
   npm run dev
   ```

3. **Open your browser** and navigate to `http://localhost:3000`

4. **Paste your transcript JSON** in the format:
   ```json
   [
     {"role": "user", "content": "Hello"},
     {"role": "assistant", "content": "Hi, how can I help you?"}
   ]
   ```

5. **Click "Classify Disposition"** to get the classification results

## API Endpoint

### POST `/disposition`

Classifies a call transcript and returns the disposition code, confidence score, explanation, summary, and key points.

**Request Body:**
```json
[
  {"role": "user", "content": "..."},
  {"role": "assistant", "content": "..."}
]
```

**Response:**
```json
{
  "Disposition_code": "PTP_ON_SPECIFIC_DATE",
  "confidence": 0.95,
  "explanation": "...",
  "summary": "...",
  "key_points": ["...", "..."]
}
```

## Development

### Backend Development

The backend uses FastAPI with the following main components:
- `Disposition_classifier_agnet.py` - Main classification agent
- `connection_status.py` - Connection status detection
- `summary_agent.py` - Transcript summarization
- `grivance_agent.py` - Grievance detection and categorization
- `preprocess_csv.py` - CSV data preprocessing

### Frontend Development

The frontend is built with React and Vite:
- `src/App.jsx` - Main application component
- `src/components/TranscriptForm.jsx` - Transcript input form
- `src/components/ResultsDisplay.jsx` - Results display component

## Environment Variables

Create a `.env` file in the root directory with:

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4
```



