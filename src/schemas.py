from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Mensaje o pregunta enviada al agente.",
        examples=["¿Javier tiene experiencia con Apache Spark?"]
    )
    history: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Historial previo de la conversación para soporte multi-turno."
    )


class HerramientaEjecutada(BaseModel):
    herramienta: str
    argumentos: Dict[str, Any]
    resultado_extracto: str


class ConsumoTokens(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatResponse(BaseModel):
    status: str = Field(default="success", description="Estado de la respuesta.")
    response: str = Field(..., description="Respuesta final redactada por el agente.")
    tools_used: List[HerramientaEjecutada] = Field(
        default_factory=list,
        description="Lista de herramientas ejecutadas durante el ciclo de razonamiento."
    )
    iterations: int = Field(..., description="Número de iteraciones completadas en el bucle ReAct.")
    usage: ConsumoTokens = Field(
        default_factory=ConsumoTokens,
        description="Tokens de entrada, salida y totales consumidos en la consulta."
    )


class HealthResponse(BaseModel):
    status: str
    model: str
    version: str
