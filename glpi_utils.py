import requests
import re
from github_utils import obtener_github

def conectar_glpi_jaher():
    config, _ = obtener_github("config_glpi.json")
    if not config or "url_glpi" not in config:
        return None, "Fallo: El link de túnel en GitHub no existe."
    
    base_url = config["url_glpi"]
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Origin': base_url,
        'Referer': f"{}/front/login.php"
    })

    usuario = "soporte1"
    clave = "Cpktnwt1986@*."

    try:
        login_page = session.get(f"{}/front/login.php", timeout=10)
        csrf_token = ""
        csrf_match = re.search(r'name="_glpi_csrf_token" value="([^"]+)"', login_page.text)
        if csrf_match: csrf_token = csrf_match.group(1)

        payload = {'noAuto': '0', 'login_name': usuario, 'login_password': clave, '_glpi_csrf_token': csrf_token, 'submit': 'Enviar'}
        response = session.post(f"{}/front/login.php", data=payload, allow_redirects=True)

        if session.cookies.get('glpi_session'):
            if "selectprofile.php" in response.url:
                p_match = re.search(r'profiles_id=([0-9]+)[^>]*>Soporte Técnico', response.text, re.IGNORECASE)
                p_id = p_match.group(1) if p_match else "4"
                session.get(f"{}/front/selectprofile.php?profiles_id={}")
            return session, base_url
        return None, "Fallo de autenticación."
    except Exception as e:
        return None, f"Error de red GLPI: {str(e)}"
