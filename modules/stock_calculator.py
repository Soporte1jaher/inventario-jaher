"""
modules/stock_calculator.py
Lógica de cálculo de stock, clasificación y procesamiento de datos
"""
import pandas as pd

class StockCalculator:
    """Calculador de stock e inventario"""
    
    @staticmethod
    def extraer_generacion(procesador):
        """
        Clasifica un procesador como 'obsoleto' o 'moderno'
        
        Args:
            procesador: String con el nombre del procesador
        
        Returns:
            str: 'obsoleto' o 'moderno'
        """
        if not procesador or str(procesador).strip().lower() in ['n/a', '', 'nan']:
            return 'moderno'  # Si no sabemos, lo tratamos como moderno
        
        p = str(procesador).lower()
        
        # Lista de términos para equipos antiguos
        obsoletos = ['4th', '5th', '6th', '7th', '8th', '9th', 
                     '4ta', '5ta', '6ta', '7ta', '8va', '9na', 
                     'gen 8', 'gen 9']
        
        if any(x in p for x in obsoletos):
            return 'obsoleto'
        
        # Si detecta 10, 11, 12, 13, 14 es moderno
        modernos = ['10th', '11th', '12th', '13th', '14th', 
                    '10ma', '11va', '12va', '13va', '14va', 
                    'gen 10', 'gen 11', 'gen 12']
        
        if any(x in p for x in modernos):
            return 'moderno'
        
        return 'moderno'  # Por defecto, moderno
    
    @staticmethod
    def calcular_stock_completo(df):
        """
        Calcula el stock completo: periféricos, bodega, dañados
        
        Args:
            df: DataFrame con el historial completo
        
        Returns:
            tuple: (df_stock, df_bodega, df_danados, df_completo)
        """
        if df is None or df.empty:
            return (pd.DataFrame(), pd.DataFrame(), 
                    pd.DataFrame(), pd.DataFrame())
        
        df_c = df.copy()
        df_c.columns = df_c.columns.str.lower().str.strip()
        
        # Limpieza estricta
        for col in df_c.columns:
            df_c[col] = df_c[col].astype(str).str.lower().str.strip()
        
        df_c['cant_n'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(0)
        
        # CRÍTICO: Clasificar generación de CPU
        df_c['gen_cpu'] = df_c['procesador'].apply(StockCalculator.extraer_generacion)
        
        # Definiciones de tipos
        perifericos_list = [
            'mouse', 'teclado', 'cable', 'hdmi', 'limpiador',
            'cargador', 'toner', 'tinta', 'parlante', 'herramienta'
        ]
        
        # Máscaras Booleanas
        es_periferico = df_c['equipo'].str.contains('|'.join(perifericos_list), na=False)
        es_dañado = df_c['estado'].str.contains('dañado|obsoleto|chatarrización', na=False)
        es_destino_bodega = df_c['destino'] == 'bodega'
        
        # --- 1. STOCK (Solo Periféricos para balance) ---
        df_p = df_c[es_periferico].copy()
        
        if not df_p.empty:
            def procesar_saldo(row):
                t = row['tipo']
                if any(x in t for x in ['recibido', 'ingreso', 'entrada', 'llegó']):
                    return row['cant_n']
                if any(x in t for x in ['enviado', 'salida', 'despacho', 'egreso', 'envio']):
                    return -row['cant_n']
                return 0
            
            df_p['val'] = df_p.apply(procesar_saldo, axis=1)
            st_res = (
                df_p.groupby(['equipo', 'marca', 'modelo'])
                .agg({'val': 'sum'})
                .reset_index()
            )
            st_res = st_res[st_res['val'] > 0]
        else:
            st_res = pd.DataFrame(columns=['equipo', 'marca', 'modelo', 'val'])
        
        # --- 2. BODEGA (Solo Equipos MODERNOS en Bodega) ---
        bod_res = df_c[
            es_destino_bodega &
            ~es_periferico &
            ~es_dañado &
            (df_c['gen_cpu'] == 'moderno')
        ].copy()
        
        # --- 3. DAÑADOS / OBSOLETOS ---
        danados_res = df_c[es_dañado | (df_c['gen_cpu'] == 'obsoleto')].copy()
        
        return st_res, bod_res, danados_res, df_c
    
    @staticmethod
    def aplicar_reglas_obsolescencia(borrador):
        """
        Aplica reglas de obsolescencia automática al borrador
        
        Args:
            borrador: Lista de items en el borrador
        
        Returns:
            list: Borrador actualizado con reglas aplicadas
        """
        for item in borrador:
            proc = item.get("procesador", "")
            gen = StockCalculator.extraer_generacion(proc)
            
            if gen == "obsoleto":
                item["estado"] = "Obsoleto / Pendiente Chatarrización"
                item["destino"] = "CHATARRA / BAJA"
                item["origen"] = item.get("origen", "Bodega")
        
        return borrador
