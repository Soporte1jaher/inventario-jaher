import requests
import re
from github_utils import obtener_github, enviar_github_directo

# ==========================================
# PEDIDOS A PC LOCAL
# ==========================================

def solicitar_busqueda_glpi(serie):
    pedido = {
        "serie_a_buscar": serie,
        "info": "",
        "estado": "pendiente"
    }
    return enviar_github_directo("pedido.json", pedido, f"LAIA: Solicitud serie {serie}")


def revisar_respuesta_glpi():
    contenido, _ = obtener_github("pedido.json")
    if isinstance(contenido, dict) and contenido.get("estado") == "completado":
        return contenido
    return None


# ==========================================
# CONEXIÓN DIRECTA GLPI (WEB SCRAPING)
# ==========================================

def conectar_glpi_jaher():
    config, _ = obtener_github("config_glpi.json")
    if not config or "url_glpi" not in config:
        return None, "No existe config_glpi.json"

    base_url = config["url_glpi"]
    session = requests.Session()

    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Origin": base_url,
        "Referer": f"{base_url}/front/login.php"
    })

    usuario = "soporte1"
    clave = "Cpktnwt1986@*."

    try:
        login_page = session.get(f"{base_url}/front/login.php", timeout=10)
        csrf_match = re.search(r'name="_glpi_csrf_token" value="([^"]+)"', login_page.text)
        csrf_token = csrf_match.group(1) if csrf_match else ""

        payload = {
            "noAuto": "0",
            "login_name": usuario,
            "login_password": clave,
            "_glpi_csrf_token": csrf_token,
            "submit": "Enviar"
        }

        response = session.post(f"{base_url}/front/login.php", data=payload, allow_redirects=True)

        if session.cookies.get("glpi_session"):
            return session, base_url
        else:
            return None, "Credenciales inválidas"

    except Exception as e:
        return None, str(e)


def consultar_datos_glpi(serie):
    session, base_url = conectar_glpi_jaher()
    if not session:
        return None

    url_busqueda = f"{base_url}/front/allassets.php?contains%5B0%5D={serie}&itemtype=all"

    try:
        resp = session.get(url_busqueda, timeout=10)
        if serie.lower() in resp.text.lower():
            return {"status": "Encontrado", "msg": f"Equipo {serie} detectado en GLPI."}
        return None
    except:
        return None
