import os
import requests
from fastapi import FastAPI, Request, Response
import google.generativeai as genai

app = FastAPI()

# Configuración de Credenciales Reales
GEMINI_API_KEY = "AQ.Ab8RN6KoAdpJ74sbGhbxEBAlrzvlQ6bRts9dBOxo_owqYvBwsw"
WHATSAPP_TOKEN = "EAAXRTQQ8g9YBR7RpRl3dfZAUtjbxeGFWsELZCPKs6OSdBExunhj1RZBACKL775igIN9MbNvs0aoox7uVaiBHEuZALZBlYEdV5quX8B0ZBZBscZBvPGVRTcHjFUXITWKPSM3SgBl9aMJmkf23cwYngkY81S3B11TPUfcK9n5UZABriFqFnBUZC7sdsPdewSUl8DzdIi9H6xgDCpnfYVPxY5uyZACHaLU89JWGwbsLjGY3aFtZCblK0yxhAbUJXgqWZBcwPAliQr5uW2crNehPT9CQOs8s2tY2d"
PHONE_NUMBER_ID = "1629330904797588"
VERIFY_TOKEN = "alio_token_secreto_2026"

# Configurar IA de Google Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Base de datos temporal en memoria para la simulación del Onboarding
DB_USUARIOS = {}

def enviar_mensaje_whatsapp(telefono_destino, texto):
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": telefono_destino,
        "type": "text",
        "text": {"body": texto}
    }
    try:
        response = requests.post(url, json=data, headers=headers)
        print(f"--> RESPUESTA ENVÍO WHATSAPP: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"--> ERROR AL ENVIAR WHATSAPP: {str(e)}")

@app.get("/")
async def root():
    return {"status": "ALIO backend is running perfectly"}

@app.get("/webhook")
async def verificar_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("--> WEBHOOK VALIDADO CORRECTAMENTE CON META ✅")
        return Response(content=challenge, media_type="text/plain")
    print("--> ERROR DE VALIDACIÓN EN EL WEBHOOK")
    return Response(content="Verification failed", status_code=403)

@app.post("/webhook")
async def recibir_mensaje(request: Request):
    print("📥 ¡CONEXIÓN DETECTADA EN EL WEBHOOK!")
    try:
        body = await request.json()
        print(f"--> DATOS RECIBIDOS DESDE META: {body}")
        
        # Verificar que el JSON contenga un mensaje válido
        if "object" in body and body["object"] == "whatsapp_business_account":
            for entry in body.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    if "messages" in value:
                        for message in value["messages"]:
                            telefono = message["from"]
                            texto_usuario = message.get("text", {}).get("body", "").strip()
                            
                            print(f"--> MENSAJE DE: {telefono} | CONTENIDO: {texto_usuario}")
                            
                            # Lógica de la conversación (ALIO)
                            if telefono not in DB_USUARIOS:
                                DB_USUARIOS[telefono] = {"estado": "INICIO"}
                                saludo = (
                                    "¡Hola! Bienvenido a ALIO, tu asistente financiero virtual. 🚀\n\n"
                                    "Para ayudarte a cuidar tu bolsillo, primero cuéntame:\n"
                                    "¿Cómo vas a usar esta herramienta?\n\n"
                                    "Escribe el número de tu opción:\n"
                                    "1️⃣ Uso Personal (Controlar mis gastos diarios)\n"
                                    "2️⃣ Uso de Negocio (Llevar las cuentas de mi emprendimiento)"
                                )
                                enviar_mensaje_whatsapp(telefono, saludo)
                            else:
                                estado_actual = DB_USUARIOS[telefono]["estado"]
                                if estado_actual == "INICIO":
                                    if texto_usuario == "1":
                                        DB_USUARIOS[telefono]["estado"] = "ESPERANDO_INGRESO"
                                        DB_USUARIOS[telefono]["tipo_perfil"] = "Personal"
                                        respuesta = "¡Excelente! Elegiste perfil Personal. 👤\nComencemos configurando tu presupuesto. ¿De cuánto son tus ingresos mensuales aproximados? (Ej: 'Gano 2.500.000')"
                                    elif texto_usuario == "2":
                                        DB_USUARIOS[telefono]["estado"] = "ESPERANDO_INGRESO"
                                        DB_USUARIOS[telefono]["tipo_perfil"] = "Negocio"
                                        respuesta = "¡Perfecto! Elegiste perfil de Negocio. 💼\nComencemos a organizar las finanzas de tu emprendimiento. ¿De cuánto son tus ingresos o ventas mensuales estimadas? (Ej: 'Vendo 5 millones al mes')"
                                    else:
                                        respuesta = "Por favor, selecciona una opción válida:\nEscribe 1️⃣ para Uso Personal o 2️⃣ para Uso de Negocio."
                                    enviar_mensaje_whatsapp(telefono, respuesta)
                                    
        return {"status": "success"}
    except Exception as e:
        print(f"--> ERROR CRÍTICO EN PROCESAMIENTO: {str(e)}")
        return Response(content="Internal Server Error", status_code=500)
