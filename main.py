from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from src.api.routes import router
from src.api.errors import add_exception_handlers

app = FastAPI(
    title="The Interview Agent",
    version="0.1.0",
    description="AI-powered technical interview system for VICODATHON 2026"
)

# Register exception handlers
add_exception_handlers(app)

# Include the interview router
app.include_router(router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}