import json
from pathlib import Path
from typing import Any, Dict

# Rutas absolutas a los datos
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PERFIL_PATH = DATA_DIR / "perfil.json"
PROYECTOS_DIR = DATA_DIR / "proyectos"


def _cargar_perfil() -> Dict[str, Any]:
    with open(PERFIL_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def verificar_stack_tecnologico(tecnologia: str) -> str:
    """
    Verifica de forma determinista si Javier domina o no una tecnología específica.
    """
    perfil = _cargar_perfil()
    tec_busqueda = tecnologia.strip().lower()

    # 1. Comprobar tecnologías fuera de alcance (regla anti-alucinación)
    for fuera in perfil.get("tecnologias_fuera_de_alcance", []):
        if tec_busqueda in fuera.lower():
            return (
                f"VERIFICACIÓN: Javier NO cuenta con experiencia en '{tecnologia}'. "
                f"Esta tecnología está registrada explícitamente fuera de su alcance profesional."
            )

    # 2. Comprobar stack tecnológico dominado
    stack = perfil.get("stack_tecnologico", {})
    coincidencias = []
    for categoria, items in stack.items():
        for item in items:
            if tec_busqueda in item.lower():
                coincidencias.append(f"{item} (Categoría: {categoria})")

    if coincidencias:
        return (
            f"VERIFICACIÓN POSITIVA: Javier cuenta con experiencia confirmada en '{tecnologia}'. "
            f"Coincidencias encontradas: {', '.join(coincidencias)}."
        )

    return (
        f"VERIFICACIÓN NEUTRA: La tecnología '{tecnologia}' no aparece registrada en el stack principal "
        f"ni en la lista de exclusiones de Javier. Su núcleo técnico está en Apache Spark, Python, AWS e IA Generativa."
    )


def consultar_trayectoria_detallada(tema: str) -> str:
    """
    Recupera fichas técnicas de proyectos para responder con evidencias detalladas (STAR).
    """
    if not PROYECTOS_DIR.exists():
        return "ERROR: El directorio de proyectos no existe."

    tema_norm = tema.strip().lower()
    archivos = list(PROYECTOS_DIR.glob("*.md"))
    resultados = []

    # Mapeo de palabras clave a nombres de archivo
    for archivo in archivos:
        contenido = archivo.read_text(encoding="utf-8")
        if tema_norm in archivo.name.lower() or tema_norm in contenido.lower():
            resultados.append(f"--- FICHA: {archivo.name} ---\n{contenido}\n")

    if resultados:
        return "\n".join(resultados)

    # Si no hubo coincidencia puntual, listar los proyectos disponibles
    disponibles = [a.name for a in archivos]
    return (
        f"No se encontró un caso específico con el término '{tema}'. "
        f"Casos de estudio disponibles: {', '.join(disponibles)}."
    )


def evaluar_ajuste_vacante(requisitos: str) -> str:
    """
    Provee una matriz de fortalezas y resumen cuantitativo para evaluar la compatibilidad con un puesto.
    """
    perfil = _cargar_perfil()
    info = perfil["informacion_personal"]
    exp = perfil["experiencia_laboral"][0]
    stack = perfil["stack_tecnologico"]

    resumen = (
        f"DATOS CLAVE PARA EVALUACIÓN DE VACANTE:\n"
        f"- Perfil: {info['titulo_profesional']} ({info['resumen_ejecutivo']})\n"
        f"- Trayectoria: 5 años en Big Data y 2+ años en Liderazgo Técnico / Scrum Master.\n"
        f"- Roles desempeñados en {exp['empresa']}: {', '.join(exp['roles_transversales'])}\n"
        f"- Core Stack: {', '.join(stack['lenguajes_y_big_data'])}.\n"
        f"- IA y LLMs: {', '.join(stack['ia_generativa_y_llms'])}.\n"
        f"- Nube y DevOps: {', '.join(stack['cloud_y_devops'])}.\n"
        f"- Gobernanza: {', '.join(stack['gobernanza_y_operacion'])}.\n"
        f"- Idiomas y Posgrado: Maestría en Telecomunicaciones (IPN) y {perfil['educacion_y_certificaciones']['idiomas']['certificacion']}.\n\n"
        f"Instrucción para el modelo: Compara los requisitos ingresados ('{requisitos}') "
        f"contra estos datos maestros y elabora una matriz objetiva de fortalezas y brechas."
    )
    return resumen


# -----------------------------------------------------------------------------
# Esquemas de Herramientas para Tool Calling (OpenAI / JSON Schema)
# -----------------------------------------------------------------------------
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "verificar_stack_tecnologico",
            "description": "Verifica si Javier domina o no una tecnología puntual, o si está expresamente fuera de su alcance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tecnologia": {
                        "type": "string",
                        "description": "Nombre de la tecnología o lenguaje a consultar (ej. 'Spark', 'Cobol', 'AWS').",
                    }
                },
                "required": ["tecnologia"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_trayectoria_detallada",
            "description": "Consulta casos de estudio reales y detalles técnicos profundos de proyectos liderados por Javier.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tema": {
                        "type": "string",
                        "description": "Término clave del caso o área técnica (ej. 'qa', 'cloudwatch', 'mallas', 'sostenibilidad').",
                    }
                },
                "required": ["tema"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "evaluar_ajuste_vacante",
            "description": "Obtiene la matriz de experiencia y habilidades maestras para contrastarla contra los requisitos de una oferta de empleo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "requisitos": {
                        "type": "string",
                        "description": "Texto con los requisitos, tecnologías o responsabilidades de la vacante a evaluar.",
                    }
                },
                "required": ["requisitos"],
            },
        },
    },
]

# Despachador de ejecución
HERRAMIENTAS_DISPONIBLES = {
    "verificar_stack_tecnologico": verificar_stack_tecnologico,
    "consultar_trayectoria_detallada": consultar_trayectoria_detallada,
    "evaluar_ajuste_vacante": evaluar_ajuste_vacante,
}


def ejecutar_herramienta(nombre: str, argumentos: Dict[str, Any]) -> str:
    """Ejecuta la función solicitada por el LLM y captura posibles errores."""
    funcion = HERRAMIENTAS_DISPONIBLES.get(nombre)
    if not funcion:
        return f"ERROR: Herramienta '{nombre}' no reconocida."
    try:
        return funcion(**argumentos)
    except Exception as e:
        return f"ERROR al ejecutar la herramienta '{nombre}': {str(e)}"
