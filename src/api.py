import json
import os
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from dotenv import load_dotenv

load_dotenv(override=True)

for var in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "LLM_MODEL", "AGENT_API_KEY"):
    val = os.environ.get(var)
    if val is not None:
        os.environ[var] = val.strip().strip('"').strip("'")

if not os.environ.get("OPENAI_BASE_URL", "").startswith(("http://", "https://")):
    os.environ["OPENAI_BASE_URL"] = "https://generativelanguage.googleapis.com/v1beta/openai/"

if not os.environ.get("LLM_MODEL"):
    os.environ["LLM_MODEL"] = "gemini-flash-lite-latest"

from src.agent import AgenteCV
from src.schemas import ChatRequest, ChatResponse, HealthResponse

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

agente_global: Optional[AgenteCV] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agente_global
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


def _extraer_texto_contenido(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        partes = []
        for bloque in content:
            if isinstance(bloque, str):
                partes.append(bloque)
            elif isinstance(bloque, dict):
                texto = bloque.get("text") or bloque.get("input_text") or ""
                if texto:
                    partes.append(str(texto))
        return "\n".join(partes).strip()
    return str(content) if content is not None else ""


def _parsear_open_responses_input(raw_input: Any) -> Tuple[str, List[Dict[str, str]]]:
    if isinstance(raw_input, str):
        return raw_input.strip(), []

    if isinstance(raw_input, list):
        mensajes: List[Dict[str, str]] = []
        for item in raw_input:
            if isinstance(item, str) and item.strip():
                mensajes.append({"role": "user", "content": item.strip()})
            elif isinstance(item, dict):
                role = item.get("role", "user")
                if role in ("user", "assistant"):
                    texto = _extraer_texto_contenido(item.get("content", ""))
                    if texto:
                        mensajes.append({"role": role, "content": texto})

        if not mensajes:
            return "", []

        if mensajes[-1]["role"] == "user":
            return mensajes[-1]["content"], mensajes[:-1]
        return mensajes[-1]["content"], mensajes[:-1]

    return "", []


@app.get("/", include_in_schema=False)
async def serve_frontend():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Interfaz web no encontrada.")
    return FileResponse(index_path)


@app.get("/health", response_model=HealthResponse, tags=["Monitoreo"])
async def health_check():
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


@app.get("/.well-known/agent-card.json", tags=["Open Responses"])
async def agent_card(request: Request):
    """Tarjeta de descubrimiento A2A / Open Responses."""
    base_url = str(request.base_url).rstrip("/")
    return {
        "name": "Agente CV - Javier Melendrez Cedillo",
        "description": (
            "Representante técnico virtual de Javier Melendrez Cedillo "
            "(Data Engineering Solutions Development Manager). Consulta experiencia en "
            "PySpark, Python, AWS, Scrum, liderazgo técnico y evaluación de vacantes."
        ),
        "url": f"{base_url}/v1",
        "version": "1.0.0",
        "capabilities": {"streaming": True},
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [
            {
                "id": "perfil-tecnico",
                "name": "Consulta de Stack y Trayectoria",
                "description": "Experiencia en Big Data, PySpark, Python, AWS, Scrum y QA."
            },
            {
                "id": "evaluar-vacante",
                "name": "Evaluación de Compatibilidad",
                "description": "Analiza requisitos de una vacante contra el perfil profesional."
            }
        ]
    }


@app.post("/v1/responses", tags=["Open Responses"])
async def open_responses_endpoint(
    request: Request,
    authorization: Optional[str] = Header(default=None)
):
    """Endpoint compatible con la especificación Open Responses ({base_url}/responses)."""
    if not agente_global:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El motor agéntico no se encuentra disponible."
        )

    expected_key = os.environ.get("AGENT_API_KEY", "").strip()
    if expected_key:
        token = (authorization or "").replace("Bearer ", "").strip()
        if token != expected_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Clave de API inválida o faltante."
            )

    body = await request.json()
    mensaje_usuario, historial_previo = _parsear_open_responses_input(body.get("input"))
    if not mensaje_usuario:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El campo 'input' debe contener al menos un mensaje de usuario válido."
        )

    instrucciones_extra = (body.get("instructions") or "").strip()
    consulta_final = (
        f"[Contexto adicional del cliente: {instrucciones_extra}]\n\n{mensaje_usuario}"
        if instrucciones_extra else mensaje_usuario
    )

    try:
        resultado = agente_global.responder(
            mensaje_usuario=consulta_final,
            historial_previo=historial_previo,
        )
    except Exception as e:
        traceback.print_exc()
        causa = f" ({type(e.__cause__).__name__}: {e.__cause__})" if e.__cause__ else ""
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fallo durante la ejecución agéntica: {str(e)}{causa}"
        )

    texto_respuesta = resultado["respuesta"]
    tokens = resultado.get("tokens_consumo") or {}
    resp_id = f"resp_{uuid.uuid4().hex[:24]}"
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"
    created_at = int(time.time())

    response_payload = {
        "id": resp_id,
        "object": "response",
        "created_at": created_at,
        "status": "completed",
        "model": agente_global.model,
        "output": [
            {
                "id": msg_id,
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": texto_respuesta,
                        "annotations": []
                    }
                ]
            }
        ],
        "usage": {
            "input_tokens": tokens.get("prompt_tokens", 0),
            "output_tokens": tokens.get("completion_tokens", 0),
            "total_tokens": tokens.get("total_tokens", 0)
        }
    }

    if body.get("stream"):
        def event_stream():
            eventos = [
                ("response.created", {"type": "response.created", "response": {**response_payload, "status": "in_progress", "output": []}}),
                ("response.output_item.added", {"type": "response.output_item.added", "output_index": 0, "item": {"id": msg_id, "type": "message", "status": "in_progress", "role": "assistant", "content": []}}),
                ("response.content_part.added", {"type": "response.content_part.added", "item_id": msg_id, "output_index": 0, "content_index": 0, "part": {"type": "output_text", "text": "", "annotations": []}}),
                ("response.output_text.delta", {"type": "response.output_text.delta", "item_id": msg_id, "output_index": 0, "content_index": 0, "delta": texto_respuesta}),
                ("response.output_text.done", {"type": "response.output_text.done", "item_id": msg_id, "output_index": 0, "content_index": 0, "text": texto_respuesta}),
                ("response.content_part.done", {"type": "response.content_part.done", "item_id": msg_id, "output_index": 0, "content_index": 0, "part": {"type": "output_text", "text": texto_respuesta, "annotations": []}}),
                ("response.output_item.done", {"type": "response.output_item.done", "output_index": 0, "item": response_payload["output"][0]}),
                ("response.completed", {"type": "response.completed", "response": response_payload}),
            ]
            for nombre_evento, data in eventos:
                yield f"event: {nombre_evento}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return response_payload


@app.post("/api/v1/chat", response_model=ChatResponse, tags=["Agente"])
async def chat_endpoint(payload: ChatRequest):
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
