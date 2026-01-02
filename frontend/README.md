# Disposition Classifier Frontend

React frontend for the Call Center Disposition Classifier API.

## Setup

1. Install dependencies:
```bash
npm install
```

2. Make sure the FastAPI backend is running on `http://localhost:8000`

3. Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Features

- Add multiple messages to create a call transcript
- Select role for each message (user/assistant/system)
- Submit transcript for classification
- View detailed results including:
  - Disposition code
  - Confidence score with visual indicator
  - Explanation
  - Summary
  - Key points

## Build for Production

```bash
npm run build
```

The built files will be in the `dist` directory.

