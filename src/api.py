import os
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from src.agent import AgenteCV
from src.schemas import ChatRequest, ChatResponse, HealthResponse

load_dotenv(override=True)

# Instancia global del agente
agente_global: Optional[AgenteCV] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agente_global
    try:
        agente_global = AgenteCV()
    except Exception as e:
        print(f"Error crítico al inicializar AgenteCV: {e}")
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fallo durante la ejecución agéntica: {str(e)}"
        )
