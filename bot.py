import os
import json
import urllib.parse
import requests
from bs4 import BeautifulSoup

# Sitios a monitorear en cada ejecución
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

# Credenciales desde GitHub Secrets
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")
WHATSAPP_PHONE = os.environ.get("WHATSAPP_PHONE")      # Ej: +5491112345678
WHATSAPP_APIKEY = os.environ.get("WHATSAPP_APIKEY")    # Clave de CallMeBot

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}


def enviar_discord(mensaje):
    if not DISCORD_WEBHOOK:
        return
    data = {"content": f"@everyone 🚨 **¡ALERTA DON OMAR!** 🚨\n{mensaje}"}
    requests.post(DISCORD_WEBHOOK, json=data, timeout=10)


def enviar_whatsapp(mensaje):
    if not WHATSAPP_PHONE or not WHATSAPP_APIKEY:
        return
    texto_codificado = urllib.parse.quote(f"🚨 ALERTA DON OMAR 🚨\n{mensaje}")
    url = (
        f"https://api.callmebot.com/whatsapp.php?"
        f"phone={WHATSAPP_PHONE}&text={texto_codificado}&apikey={WHATSAPP_APIKEY}"
    )
    requests.get(url, timeout=15)


def analizar_sitios():
    hallazgos = []

    for sitio in SITIOS:
        nombre = sitio["nombre"]
        url = sitio["url"]
        claves = sitio["palabras_clave"]

        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Limpiamos estilos para quedarnos con bloques relevantes y enlaces/botones
            for tag in soup(["style", "svg", "noscript"]):
                tag.decompose()

            for elemento in soup.find_all(["li", "div", "tr", "p", "article", "a", "button", "h1", "h2", "h3"]):
                txt = elemento.get_text(" ", strip=True)
                if 3 < len(txt) < 220:
                    if any(clave.lower() in txt.lower() for clave in claves):
                        etiqueta = f"[{nombre}] {txt}"
                        if etiqueta not in hallazgos:
                            hallazgos.append(etiqueta)

        except Exception as e:
            print(f"Error consultando {nombre} ({url}): {e}")

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
        print("No se pudo extraer información en esta ejecución (posible bloqueo temporal).")
        return

    # Primera ejecución: guarda el estado base y te avisa qué detectó en ambos sitios
    if not estado_anterior:
        guardar_estado(estado_actual)
        muestra = "\n".join(f"- {item}" for item in estado_actual[:15])
        msg = (
            f"Bot iniciado monitoreando Don Omar Oficial + AllAccess.\n"
            f"Detectados {len(estado_actual)} bloques iniciales. Muestra:\n{muestra}"
        )
        enviar_discord(msg)
        enviar_whatsapp(msg)
        return

    # Detecta cualquier línea nueva (nueva fecha, botón de compra habilitado, etc.)
    nuevos = [item for item in estado_actual if item not in estado_anterior]

    if nuevos:
        detalle = "\n".join(f"👉 {item}" for item in nuevos[:15])
        mensaje = (
            f"¡Se detectaron CAMBIOS o NUEVA FECHA para Don Omar en Argentina!\n\n"
            f"{detalle}\n\n"
            f"🎟️ AllAccess: https://www.allaccess.com.ar/event/don-omar\n"
            f"🌐 Oficial: https://donomar.com/pages/preventa"
        )
        enviar_discord(mensaje)
        enviar_whatsapp(mensaje)
        guardar_estado(estado_actual)
    else:
        print("Sin novedades en Don Omar ni en AllAccess.")


if __name__ == "__main__":
    main()
