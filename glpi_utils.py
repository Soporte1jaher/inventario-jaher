import streamlit as st
import requests
import json
import re
from github_utils import obtener_github, enviar_github_directo

def solicitar_busqueda_glpi(serie):
    """ Crea una solicitud de búsqueda en pedido.json """
    pedido = {
        "serie_a_buscar": serie,
        "info": "",
        "estado": "pendiente"
    }
    return enviar_github_directo("pedido.json", pedido, f"LAIA: Solicitud serie {}")

def revisar_respuesta_glpi():
    """ Lee el archivo de pedido para ver si la PC local ya respondió """
    contenido, _ = obtener_github("pedido.json")
    if isinstance(contenido, dict) and contenido.get("estado") == "completado":
        return contenido
    return None

def conectar_glpi_jaher():
    """ Intenta una conexión vía scraping al GLPI local mediante el túnel configurado """
    config, _ = obtener_github("config_glpi.json")
    if not config or "url_glpi" not in config:
        return None, "Fallo: El link de túnel en GitHub no existe."
    
    base_url = config["url_glpi"]
    session = requests.Session()
    
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9',
        'Origin': base_url,
        'Referer': f"{}/front/login.php"
    })

    usuario = "soporte1"
    clave = "Cpktnwt1986@*."

    try:
        # 1. Obtener Token CSRF para el Login
        login_page = session.get(f"{}/front/login.php", timeout=10)
        csrf_match = re.search(r'name="_glpi_csrf_token" value="([^"]+)"', login_page.text)
        csrf_token = csrf_match.group(1) if csrf_match else ""

        # 2. Intentar Login
        payload = {
            'noAuto': '0',
            'login_name': usuario,
            'login_password': clave,
            '_glpi_csrf_token': csrf_token,
            'submit': 'Enviar'
        }
        
        response = session.post(f"{}/front/login.php", data=payload, allow_redirects=True)

        # 3. Verificación de sesión activa
        if session.cookies.get('glpi_session'):
            if "selectprofile.php" in response.url:
                p_match = re.search(r'profiles_id=([0-9]+)[^>]*>Soporte Técnico', response.text, re.IGNORECASE)
                p_id = p_match.group(1) if p_match else "4"
                session.get(f"{}/front/selectprofile.php?profiles_id={}")
            return session, base_url
        else:
            return None, "Fallo de autenticación: Credenciales o Token inválidos."

    except Exception as e:
        return None, f"Error de red GLPI: {str(e)}"

def consultar_datos_glpi(serie):
    """ Busca la existencia de un equipo en GLPI de forma visual """
    session, base_url = conectar_glpi_jaher()
    if not session:
        return None
    
    url_busqueda = f"{}/front/allassets.php?contains%5B0%5D={}&itemtype=all"
    
    try:
        resp = session.get(url_busqueda, timeout=10)
        if serie.lower() in resp.text.lower():
            return {"status": "Encontrado", "msg": f"Equipo {} detectado en el panel de GLPI."}
        return None
    except:
        return None
