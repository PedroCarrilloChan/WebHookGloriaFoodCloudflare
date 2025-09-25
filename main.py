# main.py (Versión final para Cloudflare Workers)
import time
import requests
import json
from js import Response # Importamos el objeto Response de Cloudflare

# --- Módulos de Conexión a APIs Externas (Lógica sin cambios) ---
def buscar_cliente_smartpass(email_pedido, token):
    print("\n--- 🔎 Iniciando búsqueda de cliente en Smart Passes ---")
    if not token:
        return None, "Token de Smart Passes no configurado"

    headers = {'Content-Type': 'application/json', 'Authorization': token}
    program_id = "4886905521176576"
    list_url = f"https://pass.center/api/v1/loyalty/programs/{program_id}/customers"
    try:
        response = requests.get(list_url, headers=headers, timeout=15)
        response.raise_for_status()
        for cliente in response.json():
            if cliente.get('email') == email_pedido:
                print(f"✅ Cliente encontrado. ID: {cliente.get('id')}")
                return {"id": cliente.get('id')}, None
        return None, "El cliente no tiene una tarjeta digital instalada."
    except requests.exceptions.RequestException as e:
        error_msg = f"Error de conexión con API Smart Passes: {e}"
        print(f"❌ {error_msg}")
        return None, error_msg

def enviar_notificacion_smartpass(customer_id, message, endpoint, token, points=1):
    base_url = f"https://pass.center/api/v1/loyalty/programs/4886905521176576/customers/{customer_id}"
    url = f"{base_url}/{endpoint}"
    body = {}
    if endpoint == "message":
        body = {"message": message}
    elif endpoint == "points/add":
        body = {"points": points}

    headers = {'Content-Type': 'application/json', 'Authorization': token}
    try:
        response = requests.post(url, headers=headers, json=body, timeout=10)
        response.raise_for_status()
        print("✅ Petición a Smart Passes enviada exitosamente.")
        return True
    except requests.exceptions.RequestException as e:
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

            cliente_smartpass, error = buscar_cliente_smartpass(email_cliente, smartpass_token)
            if error:
                return Response.json({"status": "ignored", "reason": error}, status=200)

            customer_id = cliente_smartpass['id']
            estado = pedido.get('status')

            # --- Aquí va tu lógica completa de manejo de estados 
            # (Asegúrate de pasar `smartpass_token` a las llamadas de `enviar_notificacion_smartpas
            # Ejemplo:
            if estado == 'accepted':
                 mensaje = f"✅ ¡Genial! Tu pedido {pedido.get('id')} ha sido confirmado."
                 enviar_notificacion_smartpass(customer_id, mensaje, "message", smartpass_token)
                 if pedido.get('total_price', 0) >= 100:
                    enviar_notificacion_smartpass(customer_id, None, "points/add", smartpass_token, points=1)
            # ... agrega el resto de tu lógica para 'pending', 'canceled', etc.

            return Response.json({"status": "success"}, status=200)

        except Exception as e:
            print(f"🚨 ERROR INESPERADO EN EL WORKER: {e}")
            return Response.json({"error": "Error interno del servidor."}, status=500)