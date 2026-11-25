import os
import json
import urllib.parse
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

ARCHIVO_ESTADO = "estado_fechas.json"

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "").strip()
WHATSAPP_PHONE = os.environ.get("WHATSAPP_PHONE", "").strip()
WHATSAPP_APIKEY = os.environ.get("WHATSAPP_APIKEY", "").strip()
ES_PRUEBA_MANUAL = os.environ.get("EVENT_NAME") == "workflow_dispatch"


def enviar_discord(mensaje):
    if not DISCORD_WEBHOOK:
        print("⚠️ Falta DISCORD_WEBHOOK en los secretos.")
        return
    data = {"content": f"@everyone 🚨 **¡ALERTA DON OMAR!** 🚨\n{mensaje}"}
    r = requests.post(DISCORD_WEBHOOK, json=data, timeout=15)
    print(f"Respuesta Discord: {r.status_code}")


def enviar_whatsapp(mensaje):
    if not WHATSAPP_PHONE or not WHATSAPP_APIKEY:
        print("⚠️ Faltan credenciales de WhatsApp en los secretos.")
        return
    texto_corto = f"🚨 ALERTA DON OMAR 🚨\n{mensaje}"[:450]
    texto_codificado = urllib.parse.quote(texto_corto)
    url = (
        f"https://api.textmebot.com/send.php?"
        f"recipient={WHATSAPP_PHONE}&apikey={WHATSAPP_APIKEY}&text={texto_codificado}"
    )
    r = requests.get(url, timeout=20)
    print(f"Respuesta WhatsApp: {r.status_code} - {r.text[:100]}")


def extraer_bloques(html, nombre_sitio, claves):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["style", "svg", "noscript", "script"]):
        tag.decompose()

    encontrados = []
    for elemento in soup.find_all(["li", "div", "tr", "p", "article", "a", "button", "h1", "h2", "h3"]):
        txt = elemento.get_text(" ", strip=True)
        if 3 < len(txt) < 220:
            if any(clave.lower() in txt.lower() for clave in claves):
                etiqueta = f"[{nombre_sitio}] {txt}"
                if etiqueta not in encontrados:
                    encontrados.append(etiqueta)
    return encontrados


def analizar_sitios():
    hallazgos = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    }

    # 1. Web Oficial Don Omar
    try:
        resp = requests.get("https://donomar.com/pages/preventa", headers=headers, timeout=20)
        resp.raise_for_status()
        items = extraer_bloques(
            resp.text,
            "Web Oficial Don Omar",
            ["Buenos Aires", "Argentina", "Vélez", "Velez"]
        )
        hallazgos.extend(items)
        print(f"✅ Web Oficial Don Omar leída correctamente ({len(items)} bloques).")
    except Exception as e:
        print(f"❌ Error consultando Web Oficial Don Omar: {e}")

    # 2. AllAccess Argentina (con navegador Chromium real para pasar el filtro anti-bots)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                locale="es-AR"
            )
            page = context.new_page()
            page.goto("https://www.allaccess.com.ar/event/don-omar", wait_until="domcontentloaded", timeout=35000)
            page.wait_for_timeout(4000)
            html_allaccess = page.content()
            browser.close()

        items_aa = extraer_bloques(
            html_allaccess,
            "AllAccess Argentina",
            [
                "Buenos Aires", "Vélez", "Velez", "Octubre", "Noviembre",
                "Nueva función", "Nueva fecha", "Comprar", "Preventa", "Agotado"
            ]
        )
        hallazgos.extend(items_aa)
        print(f"✅ AllAccess Argentina leído correctamente ({len(items_aa)} bloques).")
    except Exception as e:
        print(f"❌ Error consultando AllAccess Argentina: {e}")

    return sorted(set(hallazgos))


def cargar_estado_anterior():
    if os.path.exists(ARCHIVO_ESTADO):
        with open(ARCHIVO_ESTADO, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def guardar_estado(datos):
    with open(ARCHIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def main():
    estado_actual = analizar_sitios()
    estado_anterior = cargar_estado_anterior()

    if not estado_actual:
        print("No se pudo extraer información en esta ejecución.")
        return

    nuevos = [item for item in estado_actual if item not in estado_anterior]

    if not estado_anterior or nuevos:
        guardar_estado(estado_actual)
        lista = nuevos if (estado_anterior and nuevos) else estado_actual
        detalle = "\n".join(f"👉 {item}" for item in lista[:6])
        titulo = "¡NUEVA FECHA o CAMBIO detectado para Don Omar!" if estado_anterior else "Bot iniciado y vigilando ambas páginas:"
        mensaje = (
            f"{titulo}\n\n"
            f"{detalle}\n\n"
            f"AllAccess: https://www.allaccess.com.ar/event/don-omar\n"
            f"Oficial: https://donomar.com/pages/preventa"
        )
        enviar_discord(mensaje)
        enviar_whatsapp(mensaje)
    elif ES_PRUEBA_MANUAL:
        msg_prueba = (
            f"✅ Prueba manual exitosa: el bot está activo y leyendo ambos sitios "
            f"({len(estado_actual)} bloques vigilados). Sin fechas nuevas por ahora."
        )
        enviar_discord(msg_prueba)
        enviar_whatsapp(msg_prueba)
    else:
        print("Sin novedades en Don Omar ni en AllAccess.")


if __name__ == "__main__":
    main()
