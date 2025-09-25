# main.py - Versión completa con Smart Passes
import json
from js import Response, fetch

# Función de logging
def log(mensaje):
    print(f"[WEBHOOK] {mensaje}")

# Función para buscar cliente en Smart Passes
async def buscar_cliente_smartpass(email_pedido, token):
    log(f"Buscando cliente: {email_pedido}")

    if not token:
        return None, "Token no configurado"

    headers = {
        'Content-Type': 'application/json', 
        'Authorization': token
    }
    program_id = "4886905521176576"
    url = f"https://pass.center/api/v1/loyalty/programs/{program_id}/customers"

    try:
        response = await fetch(url, {
            'method': 'GET',
            'headers': headers
        })

        if not response.ok:
            log(f"Error API Smart Passes: {response.status}")
            return None, f"Error API: {response.status}"

        customers = await response.json()
        log(f"Encontrados {len(customers)} clientes")

        for customer in customers:
            if customer.get('email') == email_pedido:
                log(f"Cliente encontrado: {customer.get('id')}")
                return {"id": customer.get('id')}, None

        return None, "Cliente no tiene tarjeta digital"

    except Exception as e:
        log(f"Error buscando cliente: {e}")
        return None, str(e)

# Función para enviar notificaciones a Smart Passes
async def enviar_notificacion_smartpass(customer_id, message, endpoint, token, points=1):
    base_url = f"https://pass.center/api/v1/loyalty/programs/4886905521176576/customers/{customer_id}"
    url = f"{base_url}/{endpoint}"

    body = {}
    if endpoint == "message":
        body = {"message": message}
    elif endpoint == "points/add":
        body = {"points": points}

    log(f"Enviando a Smart Passes: {endpoint}")

    headers = {
        'Content-Type': 'application/json', 
        'Authorization': token
    }

    try:
        response = await fetch(url, {
            'method': 'POST',
            'headers': headers,
            'body': json.dumps(body)
        })

        if not response.ok:
            log(f"Error enviando notificación: {response.status}")
            return False

        log("Notificación enviada exitosamente")
        return True

    except Exception as e:
        log(f"Error enviando notificación: {e}")
        return False

class App:
    async def fetch(self, request, env):
        log("=== NUEVA PETICIÓN ===")

        try:
            if request.method != 'POST':
                return Response.json({"error": "Método debe ser POST"}, status=405)

            # Obtener token
            try:
                token = env.SMARTPASSES_TOKEN
                log("Token configurado: SÍ")
            except:
                token = None
                log("Token configurado: NO")

            # Leer datos
            data = await request.json()
            log("Datos recibidos correctamente")

            # Validaciones
            if not data:
                return Response.json({"error": "No se enviaron datos"}, status=400)

            try:
                orders = data.get('orders')
                if not orders:
                    return Response.json({"error": "Falta campo 'orders'"}, status=400)
            except:
                return Response.json({"error": "Formato inválido"}, status=400)

            pedido = orders[0]
            email = pedido.get('client_email')
            estado = pedido.get('status')
            order_id = pedido.get('id')
            total_price = pedido.get('total_price', 0)

            log(f"Procesando pedido {order_id}: {email}, estado: {estado}")

            if not email:
                return Response.json({"error": "Falta email del cliente"}, status=400)

            if not token:
                log("Sin token - proceso ignorado")
                return Response.json({"status": "ignored", "reason": "Token no configurado"}, status=200)

            # Buscar cliente en Smart Passes
            cliente, error = await buscar_cliente_smartpass(email, token)
            if error:
                log(f"Cliente ignorado: {error}")
                return Response.json({"status": "ignored", "reason": error}, status=200)

            customer_id = cliente['id']

            # Procesar según el estado del pedido
            if estado == 'accepted':
                mensaje = f"✅ ¡Genial! Tu pedido {order_id} ha sido confirmado."
                await enviar_notificacion_smartpass(customer_id, mensaje, "message", token)

                if total_price >= 100:
                    log("Agregando puntos por compra >= $100")
                    await enviar_notificacion_smartpass(customer_id, None, "points/add", token, points=1)

            elif estado == 'pending':
                mensaje = f"⏳ Tu pedido {order_id} está siendo preparado."
                await enviar_notificacion_smartpass(customer_id, mensaje, "message", token)

            elif estado == 'canceled':
                mensaje = f"❌ Tu pedido {order_id} ha sido cancelado."
                await enviar_notificacion_smartpass(customer_id, mensaje, "message", token)

            elif estado == 'ready':
                mensaje = f"🍕 Tu pedido {order_id} está listo para recoger."
                await enviar_notificacion_smartpass(customer_id, mensaje, "message", token)

            elif estado == 'delivered':
                mensaje = f"🚚 Tu pedido {order_id} ha sido entregado. ¡Disfrútalo!"
                await enviar_notificacion_smartpass(customer_id, mensaje, "message", token)

            else:
                log(f"Estado no manejado: {estado}")

            result = {
                "status": "success",
                "processed": {
                    "order_id": order_id,
                    "customer_id": customer_id,
                    "status": estado
                }
            }

            log("Proceso completado exitosamente")
            return Response.json(result, status=200)

        except Exception as e:
            log(f"ERROR: {str(e)}")
            return Response.json({"error": "Error interno", "details": str(e)}, status=500)

def on_fetch(request, env):
    app = App()
    return app.fetch(request, env)