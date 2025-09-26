# main.py — Cloudflare Worker (Python Experimental)
import json
from js import fetch, Response, Headers

PROGRAM_ID = "4886905521176576"

# --- Buscar cliente en SmartPasses ---
async def buscar_cliente_smartpass(email_pedido: str, token: str):
    print(f"\n--- 🔎 Buscando cliente {email_pedido} en Smart Passes ---")
    headers = {
        "content-type": "application/json",
        "authorization": token,
    }
    list_url = f"https://pass.center/api/v1/loyalty/programs/{PROGRAM_ID}/customers"

    try:
        r = await fetch(list_url, {"method": "GET", "headers": headers})
        if not r.ok:
            txt = await r.text()
            msg = f"Smart Passes GET {r.status}: {txt}"
            print(f"❌ {msg}")
            return None, msg

        clientes = await r.json()
        # Puede ser JsProxy → convertir a dict/list de Python
        clientes = clientes.to_py() if hasattr(clientes, "to_py") else clientes

        for c in clientes:
            if c.get("email") == email_pedido:
                customer_id = c.get("id")
                print(f"✅ Cliente encontrado. ID: {customer_id}")
                return {"id": customer_id}, None

        return None, "El cliente no tiene una tarjeta digital instalada."
    except Exception as e:
        msg = f"Error de conexión con API Smart Passes: {e}"
        print(f"❌ {msg}")
        return None, msg


# --- Enviar notificación o puntos ---
async def enviar_notificacion_smartpass(customer_id: str, message: str, endpoint: str, token: str, points: int = 1):
    print(f"\n--- 📨 Enviando notificación/puntos a {customer_id} ---")
    base_url = f"https://pass.center/api/v1/loyalty/programs/{PROGRAM_ID}/customers/{customer_id}"
    url = f"{base_url}/{endpoint}"

    if endpoint == "message":
        body = {"message": message}
    elif endpoint == "points/add":
        body = {"points": points}
    else:
        print(f"❌ Endpoint no soportado: {endpoint}")
        return False

    headers = {
        "content-type": "application/json",
        "authorization": token,
    }

    try:
        r = await fetch(
            url,
            {
                "method": "POST",
                "headers": headers,
                "body": json.dumps(body),
            },
        )
        if not r.ok:
            txt = await r.text()
            print(f"❌ Smart Passes POST {r.status}: {txt}")
            return False

        print("✅ Petición a Smart Passes enviada exitosamente.")
        return True
    except Exception as e:
        print(f"❌ Error al interactuar con Smart Passes: {e}")
        return False


# --- Handler principal del Worker (FORMATO CORRECTO PARA CLOUDFLARE) ---
async def fetch(request, env, ctx):
    """
    Event handler principal que Cloudflare reconocerá automáticamente.
    Esta función debe estar en el nivel superior del módulo.
    """
    print("\n" + "=" * 50)
    print("--- 📥 INICIO DE NUEVO PROCESO DE WEBHOOK (CLOUDFLARE) ---")

    if request.method != "POST":
        return Response.json({"error": "Método debe ser POST"}, status=405)

    try:
        # Leer JSON del request (puede ser JsProxy)
        raw = await request.json()
        data = raw.to_py() if hasattr(raw, "to_py") else raw

        token = env.SMARTPASSES_TOKEN  # Debe existir como Secret en Cloudflare

        if not data or not isinstance(data.get("orders"), list) or not data["orders"]:
            return Response.json({"error": "Formato de datos inválido"}, status=400)

        pedido = data["orders"][0]
        email_cliente = pedido.get("client_email")
        if not email_cliente:
            return Response.json({"error": "El pedido no contiene email"}, status=400)

        cliente_smartpass, error = await buscar_cliente_smartpass(email_cliente, token)
        if error or not cliente_smartpass:
            return Response.json({"status": "ignored", "reason": error}, status=200)

        customer_id = cliente_smartpass["id"]

        # --- Lógica de estados ---
        estado = pedido.get("status")
        mensaje = f"Tu pedido '{pedido.get('id')}' ha sido actualizado al estado: {estado}"
        await enviar_notificacion_smartpass(customer_id, mensaje, "message", token)

        print("--- ✅ FIN DEL PROCESO DE WEBHOOK ---")
        return Response.json(
            {"status": "success", "message": f"Acción para estado '{estado}' ejecutada."}
        )

    except Exception as e:
        print(f"🚨 ERROR CAPTURADO EN FETCH: {e}")
        return Response.json(
            {"error": "Error interno del servidor", "details": str(e)}, status=500
        )


# --- Handler alternativo para scheduled events (opcional) ---
async def scheduled(event, env, ctx):
    """
    Handler para eventos programados (cron jobs)
    """
    print("🕐 Evento programado ejecutado")
    return Response.json({"status": "scheduled_task_completed"})