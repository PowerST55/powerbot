import asyncio

async def iniciar_encuesta(config, server, titulo, opciones, tiempo):
    """
    Inicializa la encuesta: limpia votos, participantes, establece título, opciones y tiempo.
    """
    config.votos.clear()
    config.participantes_votantes.clear()
    config.encuesta_activa = True

    # Redirige a la vista de encuesta antes de enviar datos para evitar parpadeos.
    await server.change_page("poll.html")
    await asyncio.sleep(0.2)  # Pequeño respiro para que cargue el cliente

    # Establecer el título de la encuesta en el servidor
    await server.settittle(titulo)

    # Añadir opciones a la encuesta en el servidor
    for opcion in opciones:
        await server.addoption(opcion)
        await asyncio.sleep(0.25)  # Ir mostrando opciones poco a poco

    # Establecer el tiempo de la encuesta en el servidor
    await server.polltime(tiempo)

def resetpoll(config):
    """
    Resetea la encuesta: desactiva, limpia votos y participantes.
    """
    config.encuesta_activa = False
    config.votos.clear()
    config.participantes_votantes.clear()
    print("Se ha terminado la encuesta.")