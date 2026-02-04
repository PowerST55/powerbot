import asyncio
import websockets
import json
import random

class WebSocketServer:
    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.clients = set()
        self.server = None
        self.running = False
        self.message_queue = asyncio.Queue()
        self.items = []
        self.participantes_ruleta = set()
        self.remove_winner = False
        self.last_winner = None
        self.mini_encuesta = False

    # --- Gestión de clientes y mensajes ---

    async def handler(self, websocket):
        """Maneja la conexión de un nuevo cliente."""
        self.clients.add(websocket)
        print("Nuevo cliente conectado")
        try:
            async for message in websocket:
                print("Mensaje recibido:", message)
                try:
                    data = json.loads(message)
                    await self.message_queue.put(data)
                except json.JSONDecodeError:
                    print("El mensaje no está en formato JSON:", message)
        except websockets.exceptions.ConnectionClosed:
            print("Cliente desconectado")
        finally:
            self.clients.remove(websocket)

    async def get_messages(self):
        """Devuelve el siguiente mensaje en la cola de WebSocket."""
        return await self.message_queue.get()

    async def send_update(self, content, timeout=3):
        """Envía un mensaje JSON a todos los clientes conectados con timeout."""
        if self.clients:
            json_data = json.dumps(content)
            try:
                await asyncio.wait_for(
                    asyncio.gather(*(client.send(json_data) for client in self.clients), return_exceptions=True),
                    timeout=timeout
                )
                print(f"[send_update] Mensaje enviado a {len(self.clients)} clientes: {content}")
            except asyncio.TimeoutError:
                print("Timeout al enviar actualización a clientes WebSocket.")
            except Exception as e:
                print(f"Error enviando actualización a clientes: {e}")
        else:
            print("[send_update] No hay clientes conectados para enviar:", content)

    # --- Funciones generales de control de página ---

    async def change_page(self, url):
        """Envía un mensaje para que los clientes cambien de página."""
        data = {"type": "redirect", "url": url}
        await self.send_update(data)

    async def ruleta_call(self):
        """Redirige a la página de la ruleta."""
        await self.change_page("ruleta.html")

    # --- Lógica de Ruleta ---

    async def add_item(self, item, url):
        """Agrega un elemento a la ruleta y lo envía a los clientes."""
        self.items.append(item)
        data = {"type": "add_item", "item": item, "url": url}
        await self.send_update(data)

    async def spin_wheel(self):
        """Gira la ruleta y envía la señal a los clientes sin bloquear el bot."""
        if not self.items:
            print("No hay elementos en la ruleta.")
            return
        angulo_random = random.uniform(0, 3600)
        desplazamiento_extra = random.uniform(0, 3600)
        rotation = 3440 + angulo_random + desplazamiento_extra
        print(rotation)
        data = {"type": "spin", "rotation": rotation}
        await self.send_update(data)

    async def reset_wheel(self):
        """Reinicia la ruleta, eliminando todos los elementos y participantes."""
        self.items.clear()
        self.participantes_ruleta.clear()
        data = {"type": "reset"}
        await self.send_update(data)

    async def keepwinner(self, value):
        """Alterna el estado de 'keep winner'."""
        data = {"type": "set_keep_winner", "value": value}
        await self.send_update(data)

    async def updaterul(self):
        """Envía una actualización general de la ruleta."""
        data = {"type": "update"}
        await self.send_update(data)

    # --- Lógica de Encuestas ---

    async def toggle_mini(self):
        """Alterna el mini modo de la encuesta y envía la actualización."""
        self.mini_encuesta = not self.mini_encuesta
        data = {"type": "toggle_mini", "value": self.mini_encuesta}
        await self.send_update(data)
        print(f"Se ha cambiado el valor de Mini Encuesta a {self.mini_encuesta}")


    async def settittle(self, value):
        """Cambia el título de la encuesta."""
        data = {"type": "tittle", "value": value}
        await self.send_update(data)

    async def addoption(self, value):
        """Añade una opción a la encuesta."""
        data = {"type": "addItem", "name": value}
        await self.send_update(data)

    async def addvote(self, value, autor):
        """Añade un voto en la encuesta."""
        print("Añadir voto recibe señal")
        data = {"type": "voteUpdate", "index": value, "autor": autor}
        await self.send_update(data)

    async def showwinner(self):
        """Finaliza la encuesta y muestra el ganador."""
        data = {"type": "pollEnd"}
        await self.send_update(data)

    async def polltime(self, time):
        """Envía el tiempo restante de la encuesta."""
        data = {"type": "polltime", "time": time}
        await self.send_update(data)

    # --- Lógica de Texthub ---

    async def addtexthub(self, text):
        """Agrega texto al texthub."""
        data = {"type": "texthubadd", "text": text}
        await self.send_update(data)

    # --- Arranque del servidor ---

    async def start(self):
        """Inicia el servidor WebSocket y lo almacena en self.server."""
        self.running = True
        self.server = await websockets.serve(self.handler, self.host, self.port)
        print(f"Servidor WebSocket corriendo en ws://{self.host}:{self.port}")

        try:
            while self.running:
                await asyncio.sleep(1)
        finally:
            await self.server.wait_closed()

# --- Ejecución directa para pruebas ---
if __name__ == "__main__":
    server = WebSocketServer()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(server.start())
