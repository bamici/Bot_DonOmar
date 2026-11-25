import os
import json
import urllib.parse
import requests
import cloudscraper
from bs4 import BeautifulSoup

SITIOS = [
    {
        "nombre": "Web Oficial Don Omar",
        "url": "https://donomar.com/pages/preventa",
        "palabras_clave": ["Buenos Aires", "Argentina", "Vélez", "Velez"]
    },
    {
        "nombre": "AllAccess Argentina",
        "url": "https://www.allaccess.com.ar/event/don-omar",
        "palabras_clave": [
            "Buenos Aires", "Vélez", "Velez", "Octubre", "Noviembre",
            "Nueva función", "Nueva fecha", "Comprar", "Preventa", "Agotado"
        ]
    }
]

ARCHIVO_ESTADO = "estado_fechas.json"

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")
WHATSAPP_PHONE = os.environ.get("WHATSAPP_PHONE")
WHATSAPP_APIKEY = os.environ.get("WHATSAPP_APIKEY")


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
    # Acortamos a 450 caracteres para evitar errores de URL larga en TextMeBot
    texto_corto = f"🚨 ALERTA DON OMAR 🚨\n{mensaje}"[:450]
    texto_codificado = urllib.parse.quote(texto_corto)
    url = (
        f"https://api.textmebot.com/send.php?"
        f"recipient={WHATSAPP_PHONE}&apikey={WHATSAPP_APIKEY}&text={texto_codificado}"
    )
    r = requests.get(url, timeout=20)
    print(f"Respuesta WhatsApp: {r.status_code} - {r.text[:100]}")


def analizar_sitios():
    hallazgos = []
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "desktop": True}
    )

    for sitio in SITIOS:
        nombre = sitio["nombre"]
        url = sitio["url"]
        claves = sitio["palabras_clave"]

        try:
            resp = scraper.get(url, timeout=25)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            for tag in soup(["style", "svg", "noscript"]):
                tag.decompose()

            for elemento in soup.find_all(["li", "div", "tr", "p", "article", "a", "button", "h1", "h2", "h3"]):
                txt = elemento.get_text(" ", strip=True)
                if 3 < len(txt) < 220:
                    if any(clave.lower() in txt.lower() for clave in claves):
                        etiqueta = f"[{nombre}] {txt}"
                        if etiqueta not in hallazgos:
                            hallazgos.append(etiqueta)

            print(f"✅ {nombre} leído correctamente.")
        except Exception as e:
            print(f"❌ Error consultando {nombre}: {e}")

    return sorted(hallazgos)


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

    if not estado_anterior:
        guardar_estado(estado_actual)
        msg = (
            f"Bot activo vigilando Don Omar Oficial y AllAccess.\n"
            f"Bloques detectados: {len(estado_actual)}.\n"
            f"Primer dato: {estado_actual[0][:120]}"
        )
        enviar_discord(msg)
        enviar_whatsapp(msg)
        return

    nuevos = [item for item in estado_actual if item not in estado_anterior]

    if nuevos:
        detalle = "\n".join(f"👉 {item}" for item in nuevos[:6])
        mensaje = (
            f"¡NUEVA FECHA o CAMBIO detectado para Don Omar!\n\n"
            f"{detalle}\n\n"
            f"AllAccess: https://www.allaccess.com.ar/event/don-omar\n"
            f"Oficial: https://donomar.com/pages/preventa"
        )
        enviar_discord(mensaje)
        enviar_whatsapp(mensaje)
        guardar_estado(estado_actual)
    else:
        print("Sin novedades en Don Omar ni en AllAccess.")


if __name__ == "__main__":
    main()
