"""
ui/stock_tab.py
Tab de control de stock (PRO) — 4 vistas: Movimientos, Stock, Bodega, Dañados
- Métricas y resúmenes
- Tabs internas con tablas limpias
- Descarga Excel 4 hojas con nombres claros
- Debug opcional (solo muestra dataframes para revisar)
"""

import streamlit as st
import pandas as pd
import datetime
import io

from modules.github_handler import GitHubHandler
from modules.stock_calculator import StockCalculator


class StockTab:
    """Tab PRO de control de stock e historial"""

    def __init__(self):
        self.github = GitHubHandler()
        self.stock_calc = StockCalculator()

    def render(self):
        st.subheader("📊 Stock Real — Control & Reportes")

        # Barra superior (acciones)
        a1, a2, a3 = st.columns([1.2, 1.2, 3.6], vertical_alignment="center")
        with a1:
            if st.button("🔄 Refrescar", use_container_width=True):
                st.rerun()

        with a2:
            # Debug = mostrar dataframes internos para revisar cálculos
            show_debug = st.toggle(
                "🧪 Debug",
                value=False,
                help="Muestra tablas internas (raw/normalizado) para detectar por qué algo sale raro."
            )

        with a3:
            st.caption("Fuente: historico.json (GitHub) → cálculo modular → vistas + Excel (4 hojas)")

        # Obtener histórico
        hist = self.github.obtener_historico()
        if not hist:
            st.info("Aún no hay datos en el histórico.")
            return

        self._mostrar_datos(hist, show_debug=show_debug)

    # ---------------------------------------------------------
    # Core
    # ---------------------------------------------------------
    def _mostrar_datos(self, hist, show_debug=False):
        df_h_raw = pd.DataFrame(hist)
        if df_h_raw.empty:
            st.info("Histórico vacío.")
            return

        # Calcular stock completo (tu lógica)
        st_res_raw, bod_res_raw, danados_res_raw, df_h_raw_out = self.stock_calc.calcular_stock_completo(df_h_raw)

        # Normalizar historial para vista (NO altera los datos guardados en GitHub)
        df_h_view = self._normalize_historial(df_h_raw_out)

        # Normalizar vistas de stock/bodega/dañados SOLO para UI
        st_res_view = self._normalize_stock(st_res_raw, mode="stock")
        bod_res_view = self._normalize_stock(bod_res_raw, mode="bodega")
        danados_res_view = self._normalize_stock(danados_res_raw, mode="danados")

        # Métricas PRO (usar VISTA normalizada, pero robusto por nombre de columna)
        self._mostrar_metricas_top(df_h_view, st_res_view, bod_res_view, danados_res_view)

        # Descarga Excel (4 hojas) — aquí puedes escoger si quieres raw o view
        # Te recomiendo EXPORTAR RAW para no perder columnas, pero con nombres bonitos de hojas.
        self._crear_boton_descarga(st_res_raw, bod_res_raw, danados_res_raw, df_h_raw_out)

        # Tabs internas
        t_mov, t_stock, t_bod, t_dan = st.tabs(
            ["🧾 Movimientos", "📦 Stock (Periféricos)", "🏢 Bodega (Cómputo)", "🧯 Dañados/Chatarras"]
        )

        with t_mov:
            self._tab_movimientos(df_h_view)

        with t_stock:
            self._tab_stock(st_res_view)

        with t_bod:
            self._tab_bodega(bod_res_view)

        with t_dan:
            self._tab_danados(danados_res_view)

        if show_debug:
            with st.expander("🧪 Debug DataFrames", expanded=False):
                st.write("df_h_raw (histórico leído):", df_h_raw.shape)
                st.dataframe(df_h_raw.head(30), use_container_width=True)
                st.write("df_h_out (histórico post-cálculo):", df_h_raw_out.shape)
                st.dataframe(df_h_raw_out.head(30), use_container_width=True)
                st.write("st_res_raw:", getattr(st_res_raw, "shape", None))
                st.dataframe(st_res_raw.head(30) if hasattr(st_res_raw, "head") else pd.DataFrame(), use_container_width=True)

    # ---------------------------------------------------------
    # UI Blocks
    # ---------------------------------------------------------
    def _mostrar_metricas_top(self, df_h, st_res, bod_res, danados_res):
        total_mov = len(df_h)

        # ---- total_stock robusto ----
        total_stock = 0
        if isinstance(st_res, pd.DataFrame) and not st_res.empty:
            if "cantidad_disponible" in st_res.columns:
                total_stock = int(pd.to_numeric(st_res["cantidad_disponible"], errors="coerce").fillna(0).sum())
            elif "val" in st_res.columns:
                total_stock = int(pd.to_numeric(st_res["val"], errors="coerce").fillna(0).sum())

        total_bodega = len(bod_res) if isinstance(bod_res, pd.DataFrame) else 0
        total_danados = len(danados_res) if isinstance(danados_res, pd.DataFrame) else 0

        # Última fecha
        ultimo = ""
        if "fecha_registro" in df_h.columns:
            try:
                ultimo_dt = pd.to_datetime(df_h["fecha_registro"], errors="coerce").max()
                if pd.notna(ultimo_dt):
                    ultimo = ultimo_dt.strftime("%Y-%m-%d %H:%M")
            except:
                ultimo = ""

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("📜 Movimientos", total_mov, help="Cantidad total de registros en el histórico.")
        k2.metric("📦 Periféricos en Stock", total_stock, help="Suma de cantidades disponibles (stock).")
        k3.metric("🏢 Registros en Bodega", total_bodega, help="Cantidad de items en la vista Bodega.")
        k4.metric("🧯 Registros Dañados/Chatarras", total_danados, help="Items marcados como dañados/obsoletos/chatarras.")

        if ultimo:
            st.caption(f"🕒 Última actividad detectada: **{ultimo}**")

        st.divider()

    def _tab_movimientos(self, df_view):
        st.markdown("### 🧾 Movimientos (Histórico)")
        if df_view.empty:
            st.warning("No hay movimientos para mostrar.")
            return
        st.dataframe(df_view.tail(250), use_container_width=True, hide_index=True)

    def _tab_stock(self, st_res):
        st.markdown("### 📦 Stock (Periféricos)")
        if st_res is None or st_res.empty:
            st.info("No hay stock disponible (o no se han registrado periféricos).")
            return

        df = st_res.copy()

        # ordenar por columna correcta
        if "cantidad_disponible" in df.columns:
            df["cantidad_disponible"] = pd.to_numeric(df["cantidad_disponible"], errors="coerce").fillna(0).astype(int)
            df = df.sort_values("cantidad_disponible", ascending=False)

        st.dataframe(df, use_container_width=True, hide_index=True)

    def _tab_bodega(self, bod_res):
        st.markdown("### 🏢 Bodega (Cómputo)")
        if bod_res is None or bod_res.empty:
            st.info("No hay registros que caigan en Bodega.")
            return
        st.dataframe(bod_res, use_container_width=True, hide_index=True)

    def _tab_danados(self, danados_res):
        st.markdown("### 🧯 Dañados / Chatarras / Bajas")
        if danados_res is None or danados_res.empty:
            st.info("No hay registros marcados como dañados/chatarras/bajas.")
            return
        st.dataframe(danados_res, use_container_width=True, hide_index=True)

    # ---------------------------------------------------------
    # Excel export (4 hojas)
    # ---------------------------------------------------------
    def _crear_boton_descarga(self, st_res, bod_res, danados_res, df_h):
        buffer = io.BytesIO()

        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            # Movimientos
            pd.DataFrame(df_h).to_excel(writer, index=False, sheet_name="MOVIMIENTOS")

            # Stock
            if isinstance(st_res, pd.DataFrame) and not st_res.empty:
                st_res.to_excel(writer, index=False, sheet_name="STOCK_SALDOS")
            else:
                pd.DataFrame(columns=["equipo", "marca", "val"]).to_excel(writer, index=False, sheet_name="STOCK_SALDOS")

            # Bodega
            if isinstance(bod_res, pd.DataFrame) and not bod_res.empty:
                bod_res.to_excel(writer, index=False, sheet_name="BODEGA")
            else:
                pd.DataFrame().to_excel(writer, index=False, sheet_name="BODEGA")

            # Dañados
            if isinstance(danados_res, pd.DataFrame) and not danados_res.empty:
                danados_res.to_excel(writer, index=False, sheet_name="DANADOS_CHATARRA")
            else:
                pd.DataFrame().to_excel(writer, index=False, sheet_name="DANADOS_CHATARRA")

        timestamp = datetime.datetime.now().strftime("%d_%m_%H%M")

        st.download_button(
            label="📥 Descargar Excel (Movimientos / Stock / Bodega / Dañados)",
            data=buffer.getvalue(),
            file_name=f"Inventario_Jaher_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    def _normalize_historial(self, df):
        df = df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]

        if "fecha_llegada" in df.columns and "fecha_registro" not in df.columns:
            df["fecha_registro"] = df["fecha_llegada"]

        if "fecha_registro" in df.columns:
            df["fecha_registro"] = pd.to_datetime(df["fecha_registro"], errors="coerce")
            df = df.sort_values("fecha_registro", ascending=True)
            df["fecha_registro"] = df["fecha_registro"].dt.strftime("%Y-%m-%d %H:%M")

        for c in ["tipo", "equipo", "marca", "modelo", "serie", "estado", "origen", "destino", "reporte", "cantidad"]:
            if c not in df.columns:
                df[c] = ""

        try:
            df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(1).astype(int)
        except:
            pass

        df = df.fillna("")

        cols_pref = [
            "fecha_registro", "tipo", "categoria_item", "equipo", "marca", "modelo", "serie",
            "cantidad", "estado", "procesador", "ram", "disco", "origen", "destino", "guia", "reporte"
        ]
        cols_pref = [c for c in cols_pref if c in df.columns]
        resto = [c for c in df.columns if c not in cols_pref]
        return df[cols_pref + resto]

    def _normalize_stock(self, df, mode="stock"):
        if df is None:
            return pd.DataFrame()

        if not isinstance(df, pd.DataFrame):
            try:
                df = pd.DataFrame(df)
            except:
                return pd.DataFrame()

        df = df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]

        # Mapear nombre de cantidad si viene como valor_final
        if "valor_final" in df.columns and "val" not in df.columns:
            df["val"] = df["valor_final"]

        if mode == "stock":
            if "equipo_f" in df.columns and "equipo" not in df.columns:
                df["equipo"] = df["equipo_f"]
            if "marca_f" in df.columns and "marca" not in df.columns:
                df["marca"] = df["marca_f"]

            cols = [c for c in ["equipo", "marca", "val"] if c in df.columns]
            if cols:
                df = df[cols]

            if "val" in df.columns:
                df = df.rename(columns={"val": "cantidad_disponible"})

        df = df.fillna("")
        return df
