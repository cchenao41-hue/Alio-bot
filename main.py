# main.py - Servidor Backend para ALIO (Tu Aliado Financiero)
from fastapi import FastAPI, Request, HTTPException
import google.generativeai as genai
import requests

app = FastAPI()

# =====================================================================
# 🔑 CONFIGURACIÓN DE CREDENCIALES REALES
# =====================================================================
GEMINI_API_KEY = "AQ.Ab8RN6KoAdpJ74sbGhbxEBAlrzvlQ6bRts9dBOxo_owqYvBwsw"
WHATSAPP_TOKEN = "EAAXRTQQ8g9YBR9LB4EeZBYDa9rVaVCKjgVhu1eDd4nNPPSbLNutp4GjI9klnVYa48SZBciNoXZCr4apljfKEAuLmSDuuTezbaPrrdS3ge6wHZAKlYddk6dflBz3JZCDphEUmNZAggfHrSgNgOq0G6469ah822ApW1fvwJiBv7uEEhRmZCxJ5YbV8ZBRRhGens5CseZCKRvXRqp38p44jCACvGsqJLBZAnCKtFGyNQ5nJ56PIP9eOxDfzUAEdDkvUi8fYVjS3kNguZBo3wXnWQg02coiXKp6"
PHONE_NUMBER_ID = "1629330904797588"

# Inicializamos el "cerebro" de Google Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Base de datos temporal en memoria para el MVP
BD_USUARIOS = {}

def obtener_o_crear_usuario(id_whatsapp: str):
    if id_whatsapp not in BD_USUARIOS:
        BD_USUARIOS[id_whatsapp] = {
            "estado": "START",
            "tipo_perfil": None, 
            "ingresos": 0,
            "gastos_fijos": {},
            "deudas_bancarias": [],
            "deudas_personas": []
        }
    return BD_USUARIOS[id_whatsapp]

# =====================================================================
# 💬 LÓGICA DE INTELIGENCIA ARTIFICIAL (GEMINI)
# =====================================================================
def consultar_a_gemini(instruccion_sistema: str, mensaje_usuario: str) -> str:
    try:
        prompt = f"{instruccion_sistema}\n\nUsuario dice: {mensaje_usuario}\nRespuesta abreviada y clara:"
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"❌ Error llamando a Gemini: {e}")
        return "Lo siento, tuve un pequeño problema técnico procesando tu mensaje. ¿Podrías repetirlo?"

# =====================================================================
# 🚀 WEBHOOK PRINCIPAL (Punto de contacto con Meta/WhatsApp)
# =====================================================================
@app.get("/")
async def ruta_raiz():
    """Agregamos esto para comprobar rápidamente en el navegador que el servidor responde"""
    return {"status": "ALIO backend está corriendo con éxito en la raíz!"}

@app.get("/webhook")
async def verificar_webhook(request: Request):
    params = request.query_params
    verify_token = "alio_token_secreto_2026" 
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == verify_token:
        print("✅ Webhook verificado con éxito por Meta!")
        return int(params.get("hub.challenge"))
    raise HTTPException(status_code=403, detail="Token de verificación inválido")

@app.post("/webhook")
async def recibir_mensaje_whatsapp(request: Request):
    body = await request.json()
    
    # 🔍 LOG CONTROL: Esto imprimirá absolutamente todo lo que Meta mande a Render
    print("📥 ¡LLEGÓ ALGO DESDE WHATSAPP! Datos recibidos:")
    print(body)
    
    # Validar que sea una notificación válida de WhatsApp
    if "entry" not in body:
        return {"status": "no_es_un_evento_de_entry_valido"}

    try:
        entry = body["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        
        # Verificar si hay mensajes en el paquete
        if "messages" not in value:
            return {"status": "no_contiene_mensajes_nuevos"}
            
        message = value["messages"][0]
        id_whatsapp = message["from"]
        
        # Asegurarnos de que el mensaje sea de tipo texto
        if message.get("type") == "text":
            mensaje_usuario = message["text"]["body"].strip()
        else:
            return {"status": "el_mensaje_no_es_texto_plano"}
            
    except Exception as e:
        print(f"⚠️ Error procesando la estructura del JSON de Meta: {e}")
        return {"status": "error_estructura_json"}

    usuario = obtener_o_crear_usuario(id_whatsapp)
    estado_actual = usuario["estado"]
    respuesta_bot = ""

    print(f"👤 Mensaje de [{id_whatsapp}] en estado [{estado_actual}]: '{mensaje_usuario}'")

    # --- PASO 0: BIFURCACIÓN DE PERFIL ---
    if estado_actual == "START":
        respuesta_bot = (
            "¡Hola! Soy *ALIO*, tu asistente y aliado financiero en WhatsApp. 🚀\n\n"
            "Para ayudarte a controlar mejor tu dinero, cuéntame:\n\n"
            "1️⃣ *Uso Personal* (Mis gastos diarios, arriendo, hogar, deudas propias).\n"
            "2️⃣ *Uso de Negocio* (Ventas de mi comercio, proveedores, arriendo del local, nómina).\n\n"
            "_Por favor, responde enviando solo el número 1 o 2._"
        )
        usuario["estado"] = "ESPERANDO_PERFIL"

    elif estado_actual == "ESPERANDO_PERFIL":
        if mensaje_usuario == "1":
            usuario["tipo_perfil"] = "PERSONAL"
            respuesta_bot = "¡Excelente! Creemos tu presupuesto *Personal*. 👤 ¿De cuánto son tus ingresos mensuales aproximados o tu sueldo?"
            usuario["estado"] = "ESPERANDO_INGRESO"
        elif mensaje_usuario == "2":
            usuario["tipo_perfil"] = "NEGOCIO"
            respuesta_bot = "¡Excelente! Creemos el presupuesto de tu *Negocio*. 💼 ¿Cuánto vendes aproximadamente en un mes normal?"
            usuario["estado"] = "ESPERANDO_INGRESO"
        else:
            respuesta_bot = "Por favor, selecciona una opción válida. Escribe *1* para Personal o *2* para Negocio."

    # --- PASO 1: INGRESOS ---
    elif estado_actual == "ESPERANDO_INGRESO":
        instruccion = "Extrae únicamente el valor numérico entero del texto del usuario. Si dice 'gano 2 millones y medio' devuelve '2500000'. Si dice '1.200.000' devuelve '1200000'. Devuelve SOLO el número, absolutamente nada de texto adicional."
        monto_texto = consultar_a_gemini(instruccion, mensaje_usuario)
        
        try:
            usuario["ingresos"] = int(''.join(filter(str.isdigit, monto_texto)))
        except ValueError:
            usuario["ingresos"] = 0 
        
        if usuario["tipo_perfil"] == "PERSONAL":
            respuesta_bot = (
                "¡Registrado! Ahora hablemos de tus gastos fijos del mes. 🏠\n\n"
                "Por favor, dime cuánto destinas aproximadamente a: *Arriendo/Vivienda, Alimentación, Servicios públicos y Telefonía celular*, o si pagas *Cuotas alimentarias*.\n\n"
                "Puedes escribírmelo todo en un solo mensaje de forma natural (Ej: 'De arriendo pago 800mil, comida 400mil, servicios 150mil')."
            )
        else:
            respuesta_bot = (
                "¡Registrado! Ahora hablemos de los costos fijos de tu negocio. 🏢\n\n"
                "Por favor, dime cuánto destinas al mes a: *Arriendo del local, Servicios comerciales, Nómina/Sueldos o Proveedores fijos*.\n\n"
                "Puedes escribírmelo todo en un solo mensaje de forma natural (Ej: 'Local 1 millón, luz 200 mil, empleados 2 millones')."
            )
        usuario["estado"] = "ESPERANDO_GASTOS_FIJOS"

    # --- PASO 2: GASTOS FIJOS ---
    elif estado_actual == "ESPERANDO_GASTOS_FIJOS":
        instruccion = f"El usuario está configurando sus gastos fijos para un perfil {usuario['tipo_perfil']}. Extrae las categorías y montos mencionados y resume lo que entendiste de forma muy breve y amigable, confirmando los valores en una lista con viñetas limpias."
        resumen_ia = consultar_a_gemini(instruccion, mensaje_usuario)
        usuario["gastos_fijos"] = {"registro": mensaje_usuario}
        
        respuesta_bot = (
            f"¡Entendido! Esto fue lo que registré:\n\n{resumen_ia}\n\n"
            "💳 Ahora organicemos tus deudas financieras.\n\n"
            "¿Tienes tarjetas de crédito o préstamos bancarios vigentes? Si es así, lístame el nombre del banco/tarjeta y la cuota mensual (Ej: 'Tarjeta Visa 120.000 y Crédito 450.000'). Si no tienes, escribe *'No'*."
        )
        usuario["estado"] = "ESPERANDO_DEUDAS_BANCO"

    # --- PASO 3: DEUDAS BANCARIAS ---
    elif estado_actual == "ESPERANDO_DEUDAS_BANCO":
        if mensaje_usuario.lower() != "no":
            usuario["deudas_bancarias"].append(mensaje_usuario)
            
        if usuario["tipo_perfil"] == "PERSONAL":
            respuesta_bot = (
                "Guardado. 👥 Por último, ¿le debes dinero a personas naturales (amigos, familiares o conocidos)?\n\n"
                "Dime a quién y la cuota mensual (Ej: 'A mi tío Carlos 100.000 y a Laura 50.000'). Si no tienes deudas de este tipo, escribe *'No'*."
            )
        else:
            respuesta_bot = (
                "Guardado. 👥 Por último, ¿el negocio le debe dinero a proveedores de mercancía por fuera del banco o préstamos a terceros?\n\n"
                "Dime a quién y la cuota (Ej: 'A distribuidora 300.000 semanales'). Si no tienes deudas de este tipo, escribe *'No'*."
            )
        usuario["estado"] = "ESPERANDO_DEUDAS_PERSONAS"

    # --- PASO 4: DEUDAS PERSONAS Y CIERRE ---
    elif estado_actual == "ESPERANDO_DEUDAS_PERSONAS":
        if mensaje_usuario.lower() != "no":
            usuario["deudas_personas"].append(mensaje_usuario)
            
        respuesta_bot = (
            "¡Todo listo! 🚀 Tu presupuesto inicial ha quedado configurado en *ALIO*.\n\n"
            "A partir de ahora, cada vez que gastes o tengas un ingreso, solo escríbemelo de manera natural "
            "(Ej: 'Acabo de pagar 15.000 de almuerzo' o 'Salió una venta de 45.000'). Yo lo registraré automáticamente y te ayudaré a mantener tus finanzas bajo control. ¡Mucho éxito!"
        )
        usuario["estado"] = "OPERATIVO"

    # Enviar la respuesta de vuelta
    enviar_mensaje_whatsapp(id_whatsapp, respuesta_bot)
    return {"status": "success"}


def enviar_mensaje_whatsapp(id_destino: str, texto: str):
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": id_destino,
        "type": "text",
        "text": {"body": texto}
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"📤 Respuesta de envío WhatsApp: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error enviando mensaje por WhatsApp: {e}")
