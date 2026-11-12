import os
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from dotenv import load_dotenv

from src.agent import AgenteCV
from src.schemas import ChatRequest, ChatResponse, HealthResponse

load_dotenv(override=True)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

agente_global: Optional[AgenteCV] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agente_global
    # Sanitizar comillas o espacios accidentales en variables inyectadas en cloud
    for var in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "LLM_MODEL"):
        val = os.environ.get(var)
        if val is not None:
            os.environ[var] = val.strip().strip('"').strip("'")

    try:
        agente_global = AgenteCV()
    except Exception as e:
        traceback.print_exc()
        raise e
    yield
    agente_global = None


app = FastAPI(
    title="API Agente CV - Javier Melendrez Cedillo",
    description="Servicio web para consulta agéntica de perfil profesional bajo estándar Open Responses.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Sirve la interfaz web conversacional del MVP."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Interfaz web no encontrada.")
    return FileResponse(index_path)


@app.get("/health", response_model=HealthResponse, tags=["Monitoreo"])
async def health_check():
    """Endpoint de verificación de salud del servicio y modelo activo."""
    if not agente_global:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El motor agéntico no está inicializado."
        )
    return HealthResponse(
        status="healthy",
        model=agente_global.model,
        version="1.0.0"
    )


@app.post("/api/v1/chat", response_model=ChatResponse, tags=["Agente"])
async def chat_endpoint(payload: ChatRequest):
    """
    Endpoint principal de inferencia agéntica.
    Recibe la consulta del usuario, ejecuta el ciclo ReAct y devuelve la respuesta estructurada.
    """
    if not agente_global:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El motor agéntico no se encuentra disponible."
        )

    try:
        resultado = agente_global.responder(
            mensaje_usuario=payload.message,
            historial_previo=payload.history,
        )

        return ChatResponse(
            status="success",
            response=resultado["respuesta"],
            tools_used=resultado["herramientas_usadas"],
            iterations=resultado["iteraciones"],
            usage=resultado["tokens_consumo"],
        )
    except Exception as e:
        traceback.print_exc()
        causa = f" ({type(e.__cause__).__name__}: {e.__cause__})" if e.__cause__ else ""
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fallo durante la ejecución agéntica: {str(e)}{causa}"
        )
