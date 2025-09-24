import os
import time
import requests
import json
from flask import Flask, request, jsonify

# --- Inicialización de la Aplicación Flask ---
app = Flask(__name__)

# --- Módulos de Conexión a APIs Externas (LÓGICA ACTUALIZADA) ---

def buscar_cliente_smartpass(email_pedido):
    """
    Busca un cliente en Smart Passes por email. Si no existe, devuelve un error.
    """
    print("\n--- 🔎 Iniciando búsqueda de cliente en Smart Passes ---")

    token = os.environ.get('SMARTPASSES_TOKEN')
    if not token:
        print("❌ Error de Configuración: El token 'SMARTPASSES_TOKEN' no está definido.")
        return None, "Token de Smart Passes no configurado"

    headers = {'Content-Type': 'application/json', 'Authorization': token}
    program_id = "4886905521176576"

    list_url = f"https://pass.center/api/v1/loyalty/programs/{program_id}/customers"

    try:
        print(f"  - Obteniendo lista de todos los clientes de: {list_url}")
        response = requests.get(list_url, headers=headers, timeout=15)
        response.raise_for_status()

        todos_los_clientes = response.json()
        print(f"  - Encontrados {len(todos_los_clientes)} clientes en total. Buscando coincidencia por email...")

        for cliente in todos_los_clientes:
            if cliente.get('email') == email_pedido:
                customer_id = cliente.get('id')
                print(f"✅ Cliente encontrado en Smart Passes. ID: {customer_id}")
                return {"id": customer_id}, None

        print("❌ Cliente no encontrado en la lista de Smart Passes.")
        return None, "El cliente no tiene una tarjeta digital instalada (no encontrado en Smart Passes)."

    except requests.exceptions.HTTPError as e:
        error_msg = f"Error HTTP [{e.response.status_code}] con API Smart Passes: {e.response.text}"
        print(f"❌ {error_msg}")
        return None, error_msg
    except requests.exceptions.RequestException as e:
        error_msg = f"Error de conexión con API Smart Passes: {e}"
        print(f"❌ {error_msg}")
        return None, error_msg

def enviar_notificacion_smartpass(customer_id, message, endpoint, points=1):
    """
    Función unificada para enviar mensajes o agregar/quitar puntos en Smart Passes.
    """
    base_url = f"https://pass.center/api/v1/loyalty/programs/4886905521176576/customers/{customer_id}"
    url = f"{base_url}/{endpoint}"

    body = {}
    if endpoint == "message":
        print(f"\n--- 📨 Iniciando envío de mensaje vía Smart Passes ---")
        body = {"message": message}
    elif endpoint == "points/add":
        print(f"\n--- ✨ Iniciando modificación de puntos ({points}) vía Smart Passes ---")
        body = {"points": points}

    token = os.environ.get('SMARTPASSES_TOKEN')
    headers = {'Content-Type': 'application/json', 'Authorization': token}

    try:
        response = requests.post(url, headers=headers, json=body, timeout=10)
        response.raise_for_status()
        print("✅ Petición a Smart Passes enviada exitosamente.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ Error al interactuar con Smart Passes: {e}")
        return False

# --- Controlador Principal del Webhook (ACTUALIZADO) ---
@app.route('/webhook/pedidos', methods=['POST'])
def webhook_gloriafood():
    """Punto de entrada principal que ahora resta puntos en cancelación."""
    print("\n\n" + "="*50)
    print("--- 📥 INICIO DE NUEVO PROCESO DE WEBHOOK ---")
    print(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
    print("="*50)

    try:
        data = request.json
        print("\n1. DATOS CRUDOS RECIBIDOS DEL WEBHOOK:")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        if not data or not isinstance(data.get('orders'), list) or not data['orders']:
            return jsonify({"error": "Formato de datos de GloriaFood inválido"}), 400

        pedido_gloriafood = data['orders'][0]

        info_pedido = {
            "id": pedido_gloriafood.get('id'), 
            "estado": pedido_gloriafood.get('status'),
            "tipo": pedido_gloriafood.get('type'),
            "ready": pedido_gloriafood.get('ready'),
            "total_price": pedido_gloriafood.get('total_price', 0)
        }
        info_cliente = {"email": pedido_gloriafood.get('client_email')}

        print("\n2. DATOS EXTRAÍDOS DEL PEDIDO:")
        print(f"  - Pedido ID: {info_pedido['id']}, Estado: '{info_pedido['estado']}'")
        print(f"  - Tipo: '{info_pedido['tipo']}', Ready: {info_pedido['ready']}")
        print(f"  - Total: ${info_pedido['total_price']}")
        print(f"  - Cliente: {info_cliente['email']}")

        if not info_cliente['email']:
            return jsonify({"error": "El pedido no contiene un email de cliente"}), 400

        cliente_smartpass, error = buscar_cliente_smartpass(info_cliente['email'])
        if error or not cliente_smartpass:
            print(f"🔴 Proceso detenido. Razón: {error}")
            return jsonify({"status": "ignored", "reason": error}), 200

        customer_id = cliente_smartpass['id']

        estado_actual = info_pedido['estado']
        tipo_pedido = info_pedido['tipo']
        pedido_ready = info_pedido['ready']
        total_precio = info_pedido['total_price']

        print(f"\n4. LÓGICA DE ESTADO (ROUTING):")
        print(f"  - Estado: '{estado_actual}', Tipo: '{tipo_pedido}', Ready: {pedido_ready}")

        # LÓGICA ESPECÍFICA PARA PEDIDOS DINE-IN (COMER EN RESTAURANTE)
        if tipo_pedido == 'dine_in':
            if estado_actual == 'pending':
                mensaje = "⏳ Tu pedido para comer en el restaurante está siendo procesado. Te confirmaremos en breve. ¡Gracias por tu paciencia!"
                enviar_notificacion_smartpass(customer_id, mensaje, "message")

            elif estado_actual == 'accepted' and pedido_ready == False:
                mensaje = f"🍽️ ¡Tu pedido ha sido confirmado! Estamos preparando tu comida y pronto estará lista para llevártela a tu mesa. Folio: {info_pedido['id']}"
                if enviar_notificacion_smartpass(customer_id, mensaje, "message"):
                    # Agregar estampilla digital si supera $100
                    if total_precio >= 100:
                        print(f"\n  - Total ${total_precio} >= $100. Agregando estampilla digital...")
                        time.sleep(2)
                        enviar_notificacion_smartpass(customer_id, None, "points/add", points=1)

            elif estado_actual == 'accepted' and pedido_ready == True:
                mensaje = f"🔔 ¡Tu comida está lista! Nuestro mesero te la llevará a tu mesa en un momento. Folio: {info_pedido['id']}"
                enviar_notificacion_smartpass(customer_id, mensaje, "message")

            elif estado_actual == 'canceled':
                print("\n  - Restando 1 punto por cancelación...")
                enviar_notificacion_smartpass(customer_id, None, "points/add", points=-1)
                print("\n  - Esperando 4 segundos antes de enviar notificación...")
                time.sleep(4)
                mensaje = "❌ Tu pedido para comer en el restaurante ha sido cancelado. Si tienes dudas, contáctanos. ¡Te esperamos pronto!"
                enviar_notificacion_smartpass(customer_id, mensaje, "message")

        # LÓGICA PARA OTROS TIPOS DE PEDIDOS (delivery, pickup, etc.)
        else:
            if estado_actual == 'pending':
                mensaje = "⏳ Tu pedido está siendo procesado. Te notificaremos cuando sea confirmado. ¡Gracias por tu paciencia!"
                enviar_notificacion_smartpass(customer_id, mensaje, "message")

            elif estado_actual == 'accepted' and pedido_ready == False:
                mensaje = f"✅ ¡Genial! Tu pedido ha sido confirmado y está en preparación. Folio del Pedido: {info_pedido['id']}"
                if enviar_notificacion_smartpass(customer_id, mensaje, "message"):
                    # Agregar estampilla digital si supera $100
                    if total_precio >= 100:
                        print(f"\n  - Total ${total_precio} >= $100. Agregando estampilla digital...")
                        time.sleep(2)
                        enviar_notificacion_smartpass(customer_id, None, "points/add", points=1)

            elif estado_actual == 'accepted' and pedido_ready == True:
                if tipo_pedido == 'pickup':
                    mensaje = f"🔔 ¡Tu pedido está listo para recoger! Puedes pasar por él cuando gustes. Folio: {info_pedido['id']}"
                elif tipo_pedido == 'delivery':
                    mensaje = f"🚗 ¡Tu pedido está listo! Nuestro repartidor saldrá en breve a entregártelo. Folio: {info_pedido['id']}"
                else:
                    mensaje = f"🔔 ¡Tu pedido está listo! Folio: {info_pedido['id']}"
                enviar_notificacion_smartpass(customer_id, mensaje, "message")

            elif estado_actual == 'canceled':
                print("\n  - Restando 1 punto por cancelación...")
                enviar_notificacion_smartpass(customer_id, None, "points/add", points=-1)
                print("\n  - Esperando 4 segundos antes de enviar notificación...")
                time.sleep(4)
                mensaje = "❌ Tu pedido ha sido cancelado. Si tienes dudas, contáctanos. ¡Esperamos ayudarte pronto!"
                enviar_notificacion_smartpass(customer_id, mensaje, "message")

        if estado_actual not in ['pending', 'accepted', 'canceled']:
            print(f"  - Estado '{estado_actual}' no reconocido. No se realiza ninguna acción.")

        print("\n" + "="*50)
        print("--- ✅ FIN DEL PROCESO DE WEBHOOK ---")
        print("="*50 + "\n\n")
        return jsonify({"status": "success", "message": f"Acción para estado '{estado_actual}' ejecutada."}), 200

    except Exception as e:
        print(f"🚨 ERROR INESPERADO Y NO CAPTURADO EN EL SERVIDOR: {e}")
        return jsonify({"error": "Ha ocurrido un error interno en el servidor."}), 500

# --- Punto de Ejecución ---
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)