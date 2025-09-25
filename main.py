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
            print("Datos recibidos correctamente")

            # Validaciones básicas usando acceso directo
            if not data:
                return Response.json({"error": "No se enviaron datos"}, status=400)

            try:
                orders = data.get('orders')
                if not orders:
                    return Response.json({"error": "Falta campo 'orders' o está vacío"}, status=400)
            except:
                return Response.json({"error": "Formato de datos inválido"}, status=400)

            pedido = orders[0]
            email = pedido.get('client_email')
            estado = pedido.get('status')
            order_id = pedido.get('id')
            total_price = pedido.get('total_price', 0)

            print(f"Email: {email}, Estado: {estado}, ID: {order_id}")

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
                    "order_id": order_id,
                    "email": email,
                    "status": estado,
                    "token_configured": token_disponible,
                    "total_price": total_price
                }
            }

            print("Enviando respuesta exitosa")
            return Response.json(result, status=200)

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"ERROR CAPTURADO: {error_msg}")
            return Response.json({"error": error_msg}, status=500)

def on_fetch(request, env):
    app = App()
    return app.fetch(request, env)