from dotenv import load_dotenv
load_dotenv()   # load .env before any route imports read os.environ

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.assisted import router as assisted_router
from backend.routes.chat import router as chat_router
from backend.routes.documents import router as documents_router
from backend.routes.match import router as match_router
from backend.routes.profile import router as profile_router
from backend.routes.translate import router as translate_router
from backend.routes.voice import router as voice_router

app = FastAPI(
    title="Scheme Sarathi API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profile_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(match_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(translate_router, prefix="/api")
app.include_router(voice_router, prefix="/api")
app.include_router(assisted_router, prefix="/api")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}