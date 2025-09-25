# main.py - Versión mínima para testing
import json
from js import Response

class App:
    async def fetch(self, request, env):
        print("=== WEBHOOK TEST INICIADO ===")

        try:
            print(f"Método: {request.method}")
            print(f"URL: {request.url}")

            if request.method != 'POST':
                return Response.json({"error": "Método debe ser POST"}, status=405)

            # Leer datos
            data = await request.json()
            print(f"Datos recibidos: {json.dumps(data)}")

            # Validaciones básicas
            if not data or 'orders' not in data:
                return Response.json({"error": "Falta campo 'orders'"}, status=400)

            if not data['orders']:
                return Response.json({"error": "orders está vacío"}, status=400)

            pedido = data['orders'][0]
            email = pedido.get('client_email')
            estado = pedido.get('status')

            print(f"Email: {email}, Estado: {estado}")

            # Verificar token de forma más simple
            try:
                token = env.SMARTPASSES_TOKEN
                token_disponible = True
            except:
                token = None
                token_disponible = False

            print(f"Token disponible: {token_disponible}")

            # Respuesta exitosa
            result = {
                "status": "success",
                "message": "Webhook recibido correctamente",
                "received_data": {
                    "order_id": pedido.get('id'),
                    "email": email,
                    "status": estado,
                    "token_configured": token_disponible,
                    "total_price": pedido.get('total_price', 0)
                }
            }

            print(f"Enviando respuesta exitosa")
            return Response.json(result, status=200)

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"ERROR CAPTURADO: {error_msg}")
            return Response.json({"error": error_msg}, status=500)

def on_fetch(request, env):
    app = App()
    return app.fetch(request, env)