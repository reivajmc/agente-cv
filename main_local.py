import sys
from src.agent import AgenteCV


def main():
    print("=" * 65)
    print(" Agente de CV - Javier Melendrez Cedillo (Modo Local Interactivo)")
    print(" Escribe 'salir' o 'exit' para terminar la sesión.")
    print("=" * 65 + "\n")

    try:
        agente = AgenteCV()
    except Exception as e:
        print(f"Error de inicialización: {e}")
        sys.exit(1)

    while True:
        try:
            pregunta = input("\n[Tú]: ").strip()
            if not pregunta:
                continue

            if pregunta.lower() in ["salir", "exit", "quit"]:
                print("\nCerrando sesión del agente. ¡Hasta luego!")
                break

            print("\n[Agente pensando...]")
            resultado = agente.responder(pregunta)

            # Mostrar si el agente decidió usar herramientas
            if resultado["herramientas_usadas"]:
                print("\n⚙️ Herramientas ejecutadas en esta consulta:")
                for item in resultado["herramientas_usadas"]:
                    print(f"  - {item['herramienta']}({item['argumentos']})")

            print(f"\n[Agente]:\n{resultado['respuesta']}")
            print(f"\n(Tokens consumidos: {resultado['tokens_consumo']['total_tokens']} | Iteraciones: {resultado['iteraciones']})")
            print("-" * 65)

        except KeyboardInterrupt:
            print("\nOperación cancelada por el usuario.")
            break
        except Exception as e:
            print(f"\nOcurrió un error al procesar la respuesta: {e}")


if __name__ == "__main__":
    main()
