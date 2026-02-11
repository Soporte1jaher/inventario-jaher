"""
ui/stock_tab.py
Interfaz del tab de control de stock
"""
import streamlit as st
import pandas as pd
import datetime
import io
from modules.github_handler import GitHubHandler
from modules.stock_calculator import StockCalculator

class StockTab:
    """Tab de control de stock e historial"""
    
    def __init__(self):
        self.github = GitHubHandler()
        self.stock_calc = StockCalculator()
    
    def render(self):
        """Renderiza el tab completo"""
        st.subheader("📊 Control de Stock e Historial")
        
        if st.button("🔄 Sincronizar Datos de GitHub"):
            st.rerun()
        
        # Obtener datos
        hist = self.github.obtener_historico()
        
        if hist:
            self._mostrar_datos(hist)
        else:
            st.info("No hay datos en el historial aún.")
    
    def _mostrar_datos(self, hist):
        """Muestra los datos del historial"""
        df_h_raw = pd.DataFrame(hist)
        
        # Calcular stock
        st_res, bod_res, danados_res, df_h = self.stock_calc.calcular_stock_completo(df_h_raw)
        
        # Métricas
        self._mostrar_metricas(st_res, df_h)
        
        # Botón de descarga Excel
        self._crear_boton_descarga(st_res, bod_res, danados_res, df_h)
        
        # Mostrar tabla
        st.write("### 📜 Últimos Movimientos en el Histórico")
        st.dataframe(df_h.tail(20), use_container_width=True)
    
    def _mostrar_metricas(self, st_res, df_h):
        """Muestra métricas del stock"""
        k1, k2 = st.columns(2)
        
        total_stock = int(st_res['val'].sum()) if not st_res.empty else 0
        k1.metric("📦 Periféricos en Stock", total_stock)
        k2.metric("🚚 Movimientos Totales", len(df_h))
    
    def _crear_boton_descarga(self, st_res, bod_res, danados_res, df_h):
        """Crea el botón de descarga del Excel"""
        buffer = io.BytesIO()
        
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            # HOJA 1: Historial Completo
            df_h.to_excel(writer, index=False, sheet_name='Enviados y Recibidos')
            
            # HOJA 2: Stock Saldos
            if not st_res.empty:
                st_res.to_excel(writer, index=False, sheet_name='Stock (Saldos)')
            
            # HOJA 3: BODEGA
            if not bod_res.empty:
                bod_res.to_excel(writer, index=False, sheet_name='BODEGA')
            
            # HOJA 4: DAÑADOS
            if not danados_res.empty:
                danados_res.to_excel(writer, index=False, sheet_name='DAÑADOS')
        
        timestamp = datetime.datetime.now().strftime('%d_%m_%H%M')
        
        st.download_button(
            label="📥 DESCARGAR EXCEL SINCRONIZADO (4 HOJAS)",
            data=buffer.getvalue(),
            file_name=f"Inventario_Jaher_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
