# main.py - Versión Final y Funcional
import json
import pyodide_http  # Adaptador para que 'requests' funcione
from js import Response

# Hacemos que pyodide_http parchee 'requests'
pyodide_http.patch_all()
import requests

# --- Módulos de Conexión a APIs Externas (LÓGICA ORIGINAL RESTAURADA) ---

def buscar_cliente_smartpass(email_pedido, token):
    print(f"\n--- 🔎 Buscando cliente {email_pedido} en Smart Passes ---")
    headers = {'Content-Type': 'application/json', 'Authorization': token}
    program_id = "4886905521176576"
    list_url = f"https://pass.center/api/v1/loyalty/programs/{program_id}/customers"
    try:
        response = requests.get(list_url, headers=headers, timeout=15)
        response.raise_for_status()
        # ¡IMPORTANTE! Convertimos la respuesta JsProxy a un diccionario de Python
        todos_los_clientes = response.json().to_py()
        for cliente in todos_los_clientes:
            if cliente.get('email') == email_pedido:
                customer_id = cliente.get('id')
                print(f"✅ Cliente encontrado. ID: {customer_id}")
                return {"id": customer_id}, None
        return None, "El cliente no tiene una tarjeta digital instalada."
    except requests.exceptions.RequestException as e:
        error_msg = f"Error de conexión con API Smart Passes: {e}"
        print(f"❌ {error_msg}")
        return None, error_msg

def enviar_notificacion_smartpass(customer_id, message, endpoint, token, points=1):
    print(f"\n--- 📨 Enviando notificación/puntos a {customer_id} ---")
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
        print("\n" + "="*50)
        print("--- 📥 INICIO DE NUEVO PROCESO DE WEBHOOK (CLOUDFLARE) ---")

        if request.method != 'POST':
            return Response.json({"error": "Método debe ser POST"}, status=405)

        try:
            # ¡LA CORRECCIÓN CLAVE! Convertimos el JsProxy a un dict de Python
            data = (await request.json()).to_py()

            token = env.SMARTPASSES_TOKEN

            # El resto de la lógica original
            if not data or not isinstance(data.get('orders'), list) or not data['orders']:
                return Response.json({"error": "Formato de datos inválido"}, status=400)

            pedido = data['orders'][0]
            email_cliente = pedido.get('client_email')

            if not email_cliente:
                return Response.json({"error": "El pedido no contiene email"}, status=400)

            cliente_smartpass, error = buscar_cliente_smartpass(email_cliente, token)
            if error or not cliente_smartpass:
                return Response.json({"status": "ignored", "reason": error}, status=200)

            customer_id = cliente_smartpass['id']

            # --- Aquí puedes añadir toda tu lógica de estados (if/elif/else) ---
            estado = pedido.get('status')
            mensaje = f"Tu pedido '{pedido.get('id')}' ha sido actualizado al estado: {estado}"
            enviar_notificacion_smartpass(customer_id, mensaje, "message", token)

            print("--- ✅ FIN DEL PROCESO DE WEBHOOK ---")
            return Response.json({"status": "success", "message": f"Acción para estado '{estado}' ejecutada."})

        except Exception as e:
            print(f"🚨 ERROR CAPTURADO EN FETCH: {e}")
            return Response.json({"error": "Error interno del servidor", "details": str(e)}, status=500)