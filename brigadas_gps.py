# --------------------------------------
# Flask App: Rastreo de brigadas (Telegram + Supabase + Render-ready)
# --------------------------------------
import os
from flask import Flask, request, jsonify, render_template
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import requests

# Cargar .env
load_dotenv()

# Inicializa Flask
app = Flask(__name__)

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_API_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# -------------------------
# Webhook de Telegram
@app.route("/webhook/telegram", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    print("[Webhook] Recibido:", data)

    try:
        message = data.get("message", {})
        user_id = message.get("from", {}).get("id")
        username = message.get("from", {}).get("username", "")
        location = message.get("location")

        print("[🆔] ID de Telegram:", user_id)

        if location:
            # Buscar datos del técnico usando el campo telegram_id (⚠️ AJUSTA si tu tabla usa otro nombre)
            perfil = supabase.table("tecnicos_telegram") \
                .select("*") \
                .eq("telegram_id", str(user_id)) \
                .execute()

            if perfil.data:
                info = perfil.data[0]
                tecnico = info.get("tecnico", "")
                brigada = info.get("brigada", "")
                contrata = info.get("contrata", "")
                print(f"[👤] Usuario registrado: {tecnico} / {brigada}")
            else:
                print("[❌] Usuario NO encontrado en tecnicos_telegram:", user_id)
                tecnico = brigada = contrata = ""

            # Guardar ubicación
            supabase.table("ubicaciones_brigadas").insert({
                "telefono": str(user_id),
                "usuario": username,
                "tecnico": tecnico,
                "brigada": brigada,
                "contrata": contrata,
                "latitud": location["latitude"],
                "longitud": location["longitude"],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }).execute()

            print(f"[📍] Ubicación guardada: {location['latitude']}, {location['longitude']}")
            return jsonify({"ok": True})

    except Exception as e:
        print(f"[!] Error en webhook: {e}")
        return jsonify({"ok": False, "error": str(e)}), 400

    return jsonify({"ok": True, "message": "Sin ubicación"}), 200


# -------------------------
# API para mostrar ubicaciones activas (últimos 10 min)
# -------------------------
@app.route("/api/ubicaciones")
def get_ubicaciones():
    now = datetime.now(timezone.utc)
    hace_10min = now - timedelta(minutes=10)

    response = supabase.table("ubicaciones_brigadas") \
        .select("*") \
        .gte("timestamp", hace_10min.isoformat()) \
        .order("timestamp", desc=True) \
        .execute()

    data = response.data or []

    # Filtrar última ubicación por técnico (telefono)
    vistos = {}
    for row in data:
        key = row.get("telefono")
        if key not in vistos:
            ts = datetime.fromisoformat(row["timestamp"])
            minutos = round((now - ts).total_seconds() / 60)
            row["minutos_transcurridos"] = minutos
            row["estado"] = "activo" if minutos <= 30 else "inactivo"
            vistos[key] = row

    return jsonify(list(vistos.values()))


# -------------------------
# Registrar Webhook en Telegram
# -------------------------
@app.route("/registrar_webhook")
def registrar_webhook():
    dominio = os.getenv("PUBLIC_URL") or "https://monitoreo-gps.onrender.com"
    url_webhook = f"{dominio}/webhook/telegram"
    url_set = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"

    r = requests.post(url_set, data={"url": url_webhook})
    print("[+] Webhook registrado:", url_webhook)
    return jsonify(r.json())


# -------------------------
# Mapa HTML
# -------------------------
@app.route("/")
def index():
    return render_template("mapa_gps.html")


# -------------------------
# Main (local debug solo)
# -------------------------
if __name__ == '__main__':
    print("🌐 SUPABASE_URL:", SUPABASE_URL)
    print("🔐 SUPABASE_API_KEY presente:", bool(SUPABASE_KEY))
    app.run(debug=True)
