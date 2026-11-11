import json
import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from openai import OpenAI

from src.prompts import obtener_system_prompt
from src.tools import TOOLS_SCHEMA, ejecutar_herramienta

load_dotenv(override=True)


class AgenteCV:
    def __init__(self, model_name: Optional[str] = None):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "tu_api_key_aqui":
            raise ValueError(
                "ERROR: Configura una clave válida en OPENAI_API_KEY dentro de tu archivo .env"
            )

        base_url = os.getenv("OPENAI_BASE_URL")
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=30.0
        ) if base_url else OpenAI(api_key=api_key, timeout=30.0)

        self.model = model_name or os.getenv("LLM_MODEL", "gemini-flash-lite-latest")
        self.system_prompt = obtener_system_prompt()

    def responder(
        self,
        mensaje_usuario: str,
        historial_previo: Optional[List[Dict[str, Any]]] = None,
        max_iteraciones: int = 5
    ) -> Dict[str, Any]:
        """
        Bucle ReAct con propagación de thought_signature para compatibilidad con Gemini.
        """
        mensajes: List[Dict[str, Any]] = [{"role": "system", "content": self.system_prompt}]

        if historial_previo:
            mensajes.extend(historial_previo)

        mensajes.append({"role": "user", "content": mensaje_usuario})

        herramientas_usadas: List[Dict[str, Any]] = []
        iteracion = 0

        while iteracion < max_iteraciones:
            iteracion += 1

            respuesta = self.client.chat.completions.create(
                model=self.model,
                messages=mensajes,
                tools=TOOLS_SCHEMA,
                tool_choice="auto",
                temperature=0.2,
            )

            eleccion = respuesta.choices[0]
            mensaje_modelo = eleccion.message

            # El modelo solicita ejecutar una o más herramientas
            if mensaje_modelo.tool_calls:
                tool_calls_payload = []
                for tc in mensaje_modelo.tool_calls:
                    tc_dict = {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    # Reenviar thought_signature exigido por Google
                    if hasattr(tc, "extra_content") and tc.extra_content:
                        tc_dict["extra_content"] = tc.extra_content

                    tool_calls_payload.append(tc_dict)

                # Se agrega el mensaje del asistente con las herramientas y firmas
                mensajes.append({
                    "role": "assistant",
                    "content": mensaje_modelo.content or "",
                    "tool_calls": tool_calls_payload,
                })

                # Ejecución de cada herramienta
                for tc in mensaje_modelo.tool_calls:
                    nombre_funcion = tc.function.name
                    argumentos_raw = tc.function.arguments

                    try:
                        argumentos = json.loads(argumentos_raw)
                    except json.JSONDecodeError:
                        argumentos = {}

                    resultado = ejecutar_herramienta(nombre_funcion, argumentos)

                    herramientas_usadas.append({
                        "herramienta": nombre_funcion,
                        "argumentos": argumentos,
                        "resultado_extracto": (resultado[:120] + "...") if len(resultado) > 120 else resultado
                    })

                    # Respuesta de la herramienta al contexto
                    mensajes.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(resultado),
                    })

                continue

            # Respuesta final lista
            return {
                "respuesta": mensaje_modelo.content or "",
                "herramientas_usadas": herramientas_usadas,
                "iteraciones": iteracion,
                "tokens_consumo": {
                    "prompt_tokens": respuesta.usage.prompt_tokens if respuesta.usage else 0,
                    "completion_tokens": respuesta.usage.completion_tokens if respuesta.usage else 0,
                    "total_tokens": respuesta.usage.total_tokens if respuesta.usage else 0,
                }
            }

        return {
            "respuesta": "Límite de iteraciones alcanzado.",
            "herramientas_usadas": herramientas_usadas,
            "iteraciones": iteracion,
            "tokens_consumo": {"total_tokens": 0}
        }
