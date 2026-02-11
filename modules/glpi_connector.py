"""
modules/glpi_connector.py
Manejo de conexiones y consultas a GLPI
"""
import requests
import re
from modules.github_handler import GitHubHandler

class GLPIConnector:
    """Conector para GLPI"""
    
    def __init__(self):
        self.github = GitHubHandler()
        self.session = None
        self.base_url = None
    
    def conectar(self):
        """
        Establece conexión con GLPI usando configuración de GitHub
        
        Returns:
            tuple: (session, base_url) o (None, mensaje_error)
        """
        config, _ = self.github.obtener_archivo("config_glpi.json")
        
        if not config or "url_glpi" not in config:
            return None, "Fallo: El link de túnel en GitHub no existe."
        
        base_url = config["url_glpi"]
        session = requests.Session()
        
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9',
            'Origin': base_url,
            'Referer': f"{base_url}/front/login.php"
        })
        
        usuario = "soporte1"
        clave = "Cpktnwt1986@*."
        
        try:
            # 1. Obtener Token CSRF
            login_page = session.get(f"{base_url}/front/login.php", timeout=10)
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
            
            response = session.post(
                f"{base_url}/front/login.php", 
                data=payload, 
                allow_redirects=True
            )
            
            # 3. Verificación de sesión activa
            if session.cookies.get('glpi_session'):
                if "selectprofile.php" in response.url:
                    p_match = re.search(
                        r'profiles_id=([0-9]+)[^>]*>Soporte Técnico', 
                        response.text, 
                        re.IGNORECASE
                    )
                    p_id = p_match.group(1) if p_match else "4"
                    session.get(f"{base_url}/front/selectprofile.php?profiles_id={p_id}")
                
                self.session = session
                self.base_url = base_url
                return session, base_url
            else:
                return None, "Fallo de autenticación: Credenciales o Token inválidos."
        
        except Exception as e:
            return None, f"Error de red GLPI: {str(e)}"
    
    def consultar_equipo(self, serie):
        """
        Busca un equipo en GLPI por número de serie
        
        Args:
            serie: Número de serie a buscar
        
        Returns:
            dict o None: Información del equipo si se encuentra
        """
        if not self.session or not self.base_url:
            session, base_url = self.conectar()
            if not session:
                return None
        else:
            session = self.session
            base_url = self.base_url
        
        url_busqueda = f"{base_url}/front/allassets.php?contains%5B0%5D={serie}&itemtype=all"
        
        try:
            resp = session.get(url_busqueda, timeout=10)
            if serie.lower() in resp.text.lower():
                return {
                    "status": "Encontrado",
                    "msg": f"Equipo {serie} detectado en el panel de GLPI."
                }
            return None
        except:
            return None
