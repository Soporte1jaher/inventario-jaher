"""
modules/ai_engine.py - Motor de IA pulido
"""
from openai import OpenAI
import json
from config.settings import Config, SYSTEM_PROMPT

class AIEngine:
    def __init__(self):
        self.client = OpenAI(api_key=Config.get_api_key())
        self.model = "gpt-4o-mini"
        self.temperature = 0
    
    def extraer_json(self, texto_completo):
        try:
            inicio = texto_completo.find("{")
            fin = texto_completo.rfind("}") + 1
            if inicio != -1:
                texto_hablado = texto_completo[:inicio].strip()
                json_puro = texto_completo[inicio:fin].strip()
                return texto_hablado, json_puro
            return texto_completo.strip(), ""
        except:
            return texto_completo.strip(), ""

    def procesar_input(self, user_input, lecciones, borrador_actual, historial_mensajes):
        # ... (Tu código de procesar_input está perfecto, mantenlo igual) ...
        memoria_err = "\n".join([f"- {l['lo_que_hizo_mal']} -> {l['como_debe_hacerlo']}" for l in lecciones]) if lecciones else ""
        contexto_tabla = json.dumps(borrador_actual, ensure_ascii=False) if borrador_actual else "[]"
        mensajes_api = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": f"LECCIONES TÉCNICAS:\n{memoria_err}"},
            {"role": "system", "content": f"ESTADO ACTUAL: {contexto_tabla}"}
        ]
        for m in historial_mensajes[-10:]: mensajes_api.append(m)
        mensajes_api.append({"role": "user", "content": user_input})
        
        response = self.client.chat.completions.create(model=self.model, messages=mensajes_api, temperature=self.temperature)
        raw_content = response.choices[0].message.content
        texto_fuera, res_txt = self.extraer_json(raw_content)
        
        try:
            res_json = json.loads(res_txt) if res_txt else {}
        except:
            res_json = {}
        
        voz_interna = res_json.get("missing_info", "")
        msg_laia = f"{texto_fuera}\n{voz_interna}".strip()
        return {"mensaje": msg_laia or "Instrucción procesada.", "json_response": res_json, "raw_content": raw_content}

    def generar_orden_borrado(self, instruccion, historial_reciente):
        """Genera orden de borrado (Exactamente como el original)"""
        contexto_breve = json.dumps(historial_reciente, ensure_ascii=False)
        prompt_db = f"""
Actúa como DBA Senior. Tu objetivo es generar un comando de borrado en JSON.
Analiza el HISTORIAL ACTUAL para encontrar qué columna y valor coinciden con la instrucción.

COLUMNAS VÁLIDAS: 'equipo', 'marca', 'modelo', 'serie', 'guia', 'destino', 'origen', 'categoria_item'.

HISTORIAL ACTUAL (Muestra): {contexto_breve}

INSTRUCCIÓN DEL USUARIO: "{instruccion}"

REGLAS DE SALIDA:
1. Si pide borrar todo: {{"accion": "borrar_todo"}}
2. Si es específico:
   - Identifica la columna que mejor encaja.
   - Genera: {{"accion": "borrar_filtro", "columna": "nombre_de_columna", "valor": "valor_exacto_encontrado_en_historial"}}

RESPONDE ÚNICAMENTE EL JSON.
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": prompt_db}],
                temperature=0
            )
            raw_res = response.choices[0].message.content.strip()
            _, json_puro = self.extraer_json(raw_res) # Usamos la función de extracción aquí también
            return json.loads(json_puro)
        except Exception as e:
            print(f"Error IA Borrado: {e}")
            return None
