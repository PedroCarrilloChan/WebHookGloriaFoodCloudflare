# main.py (Versión compatible con Cloudflare Workers)
import time
import json
from js import Response, fetch # Importamos fetch de JavaScript

# --- Módulos de Conexión a APIs Externas (Usando fetch en lugar de requests) ---
async def buscar_cliente_smartpass(email_pedido, token):
    print("\n--- 🔎 Iniciando búsqueda de cliente en Smart Passes ---")
    if not token:
        return None, "Token de Smart Passes no configurado"

    headers = {
        'Content-Type': 'application/json', 
        'Authorization': token
    }
    program_id = "4886905521176576"
    list_url = f"https://pass.center/api/v1/loyalty/programs/{program_id}/customers"

    try:
        # Usar fetch en lugar de requests
        response = await fetch(list_url, {
            'method': 'GET',
            'headers': headers
        })

        if not response.ok:
            raise Exception(f"HTTP Error: {response.status}")

        data = await response.json()

        for cliente in data:
            if cliente.get('email') == email_pedido:
                print(f"✅ Cliente encontrado. ID: {cliente.get('id')}")
                return {"id": cliente.get('id')}, None

        return None, "El cliente no tiene una tarjeta digital instalada."

    except Exception as e:
        error_msg = f"Error de conexión con API Smart Passes: {e}"
        print(f"❌ {error_msg}")
        return None, error_msg

async def enviar_notificacion_smartpass(customer_id, message, endpoint, token, points=1):
    base_url = f"https://pass.center/api/v1/loyalty/programs/4886905521176576/customers/{customer_id}"
    url = f"{base_url}/{endpoint}"

    body = {}
    if endpoint == "message":
        body = {"message": message}
    elif endpoint == "points/add":
        body = {"points": points}

    headers = {
        'Content-Type': 'application/json', 
        'Authorization': token
    }

    try:
        # Usar fetch en lugar de requests
        response = await fetch(url, {
            'method': 'POST',
            'headers': headers,
            'body': json.dumps(body)
        })

        if not response.ok:
            raise Exception(f"HTTP Error: {response.status}")

        print("✅ Petición a Smart Passes enviada exitosamente.")
        return True

    except Exception as e:
        print(f"❌ Error al interactuar con Smart Passes: {e}")
        return False

# --- Controlador Principal del Worker ---
class App:
    async def fetch(self, request, env):
        if request.method != 'POST':
            return Response.json({"error": "Método no permitido"}, status=405)

        smartpass_token = env.SMARTPASSES_TOKEN
        print("\n--- 📥 INICIO DE PROCESO DE WEBHOOK (CLOUDFLARE) ---")

        try:
            data = await request.json()

            if not data or not isinstance(data.get('orders'), list) or not data['orders']:
                return Response.json({"error": "Formato de datos inválido"}, status=400)

            pedido = data['orders'][0]
            email_cliente = pedido.get('client_email')

            if not email_cliente:
                return Response.json({"error": "El pedido no contiene email"}, status=400)

            cliente_smartpass, error = await buscar_cliente_smartpass(email_cliente, smartpass_token)
            if error:
                return Response.json({"status": "ignored", "reason": error}, status=200)

            customer_id = cliente_smartpass['id']
            estado = pedido.get('status')

            # --- Lógica completa de manejo de estados ---
            if estado == 'accepted':
                mensaje = f"✅ ¡Genial! Tu pedido {pedido.get('id')} ha sido confirmado."
                await enviar_notificacion_smartpass(customer_id, mensaje, "message", smartpass_token)

                if pedido.get('total_price', 0) >= 100:
                    await enviar_notificacion_smartpass(customer_id, None, "points/add", smartpass_token, points=1)

            elif estado == 'pending':
                mensaje = f"⏳ Tu pedido {pedido.get('id')} está siendo preparado."
                await enviar_notificacion_smartpass(customer_id, mensaje, "message", smartpass_token)

            elif estado == 'canceled':
                mensaje = f"❌ Tu pedido {pedido.get('id')} ha sido cancelado."
                await enviar_notificacion_smartpass(customer_id, mensaje, "message", smartpass_token)

            # Agrega más estados según necesites

            return Response.json({"status": "success"}, status=200)

        except Exception as e:
            print(f"🚨 ERROR INESPERADO EN EL WORKER: {e}")
            return Response.json({"error": "Error interno del servidor."}, status=500)

# Punto de entrada para Cloudflare Workers
def on_fetch(request, env):
    app = App()
    return app.fetch(request, env)