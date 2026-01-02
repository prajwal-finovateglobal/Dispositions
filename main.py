from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from Disposition_classifier_agnet import router

# Create FastAPI app
app = FastAPI()
app.include_router(router)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Disposition Classifier API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)