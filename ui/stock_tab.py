"""
ui/stock_tab.py
Stock Real — Control & Reportes (PRO)

Mejoras clave:
- 4 vistas: Movimientos / Stock / Bodega / Dañados
- Regla JAHER: si DESTINO == "bodega" -> solo se ve en BODEGA (no en MOVIMIENTOS)
  (si ORIGEN == "bodega" -> se ve normal en MOVIMIENTOS)
- Métricas top + resumen por equipo (ej: TECLADO 11, MOUSE 3)
- Debug opcional (solo para revisar dataframes)
- Export Excel 4 hojas (raw, sin perder columnas)
"""

import streamlit as st
import pandas as pd
import datetime
import io

from modules.github_handler import GitHubHandler
from modules.stock_calculator import StockCalculator


class StockTab:
    def __init__(self):
        self.github = GitHubHandler()
        self.stock_calc = StockCalculator()

    def render(self):
        # Header corporativo
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 1.1, 1.1], vertical_alignment="center")

            with c1:
                st.markdown("## 📊 Stock Real — Control & Reportes")
                st.caption("Fuente: historico.json (GitHub) → cálculo modular → vistas + Excel (4 hojas)")

            with c2:
                if st.button("🔄 Refrescar", use_container_width=True):
                    st.rerun()

            with c3:
                show_debug = st.toggle(
                    "🧪 Debug",
                    value=False,
                    help="Solo para ti: muestra dataframes crudos/post-cálculo para entender por qué algo salió raro.",
                )

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

        # Cálculo modular (tu lógica)
        st_res_raw, bod_res_raw, danados_res_raw, df_h_raw_out = self.stock_calc.calcular_stock_completo(df_h_raw)

        # Vista normalizada (UI)
        df_h_view = self._normalize_historial(df_h_raw_out)

        # ✅ Regla JAHER: si destino=bodega => sale de Movimientos
        df_mov_view = self._movimientos_sin_destino_bodega(df_h_view)

        # Normalizar tablas para UI
        st_res_view = self._normalize_stock(st_res_raw, mode="stock")
        bod_res_view = self._normalize_stock(bod_res_raw, mode="bodega")
        danados_res_view = self._normalize_stock(danados_res_raw, mode="danados")

        # Métricas + Resumen por equipo
        self._mostrar_metricas_top(df_h_view, df_mov_view, st_res_view, bod_res_view, danados_res_view)

        # Export (RAW recomendado)
        self._crear_boton_descarga(st_res_raw, bod_res_raw, danados_res_raw, df_h_raw_out)

        # Tabs internas
        t_mov, t_stock, t_bod, t_dan = st.tabs(
            ["🧾 Movimientos", "📦 Stock (Periféricos)", "🏢 Bodega (Cómputo)", "🧯 Dañados/Chatarras"]
        )

        with t_mov:
            self._tab_movimientos(df_mov_view)

        with t_stock:
            self._tab_stock(st_res_view)

        with t_bod:
            self._tab_bodega(bod_res_view)

        with t_dan:
            self._tab_danados(danados_res_view)

        # Debug opcional
        if show_debug:
            with st.expander("🧪 Debug (revisión técnica)", expanded=False):
                st.write("df_h_raw (histórico leído):", df_h_raw.shape)
                st.dataframe(df_h_raw.head(30), use_container_width=True)
                st.write("df_h_raw_out (post-cálculo):", df_h_raw_out.shape)
                st.dataframe(df_h_raw_out.head(30), use_container_width=True)
                st.write("df_h_view (normalizado UI):", df_h_view.shape)
                st.dataframe(df_h_view.head(30), use_container_width=True)
                st.write("df_mov_view (movimientos sin destino bodega):", df_mov_view.shape)
                st.dataframe(df_mov_view.head(30), use_container_width=True)

                if isinstance(st_res_raw, pd.DataFrame):
                    st.write("st_res_raw:", st_res_raw.shape)
                    st.dataframe(st_res_raw.head(30), use_container_width=True)

    # ---------------------------------------------------------
    # Métricas + resumen
    # ---------------------------------------------------------
    def _mostrar_metricas_top(self, df_h_view, df_mov_view, st_res_view, bod_res_view, danados_res_view):
        # Totales
        total_hist = len(df_h_view)
        total_mov = len(df_mov_view)

        total_stock = 0
        if isinstance(st_res_view, pd.DataFrame) and not st_res_view.empty:
            col_qty = "cantidad_disponible" if "cantidad_disponible" in st_res_view.columns else None
            if col_qty:
                total_stock = int(pd.to_numeric(st_res_view[col_qty], errors="coerce").fillna(0).sum())

        total_bodega = len(bod_res_view) if isinstance(bod_res_view, pd.DataFrame) else 0
        total_danados = len(danados_res_view) if isinstance(danados_res_view, pd.DataFrame) else 0

        # Última fecha
        ultimo = ""
        if "fecha_registro" in df_h_view.columns:
            try:
                ultimo_dt = pd.to_datetime(df_h_view["fecha_registro"], errors="coerce").max()
                if pd.notna(ultimo_dt):
                    ultimo = ultimo_dt.strftime("%Y-%m-%d %H:%M")
            except:
                ultimo = ""

        with st.container(border=True):
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("📜 Movimientos (vista)", total_mov, help="Movimientos visibles (EXCLUYE destino=bodega).")
            k2.metric("📦 Periféricos en Stock", total_stock, help="Total disponible en stock (suma).")
            k3.metric("🏢 Registros en Bodega", total_bodega, help="Items que caen en la vista Bodega.")
            k4.metric("🧯 Dañados/Chatarras", total_danados, help="Items marcados como dañados/obsoletos/chatarras.")

            if ultimo:
                st.caption(f"🕒 Última actividad detectada: **{ultimo}** | Histórico total: **{total_hist}**")

        # Resumen por equipo (lo que pediste: "11 teclados, 3 mouses...")
        if isinstance(st_res_view, pd.DataFrame) and (not st_res_view.empty) and ("equipo" in st_res_view.columns):
            with st.container(border=True):
                st.markdown("### 📌 Resumen rápido (por equipo)")
                st.caption("Ej: TECLADO 11, MOUSE 3… (calculado desde la tabla de Stock)")

                df = st_res_view.copy()
                if "cantidad_disponible" in df.columns:
                    df["cantidad_disponible"] = pd.to_numeric(df["cantidad_disponible"], errors="coerce").fillna(0).astype(int)
                    resumen = (
                        df.groupby("equipo")["cantidad_disponible"]
                        .sum()
                        .reset_index()
                        .sort_values("cantidad_disponible", ascending=False)
                    )

                    if resumen.empty:
                        st.info("No hay datos suficientes para resumen por equipo.")
                    else:
                        # mini-cards (hasta 10)
                        top = resumen.head(10)
                        cols = st.columns(min(5, len(top)))
                        for i, (_, row) in enumerate(top.iterrows()):
                            with cols[i % len(cols)]:
                                st.metric(str(row["equipo"]).upper(), int(row["cantidad_disponible"]))

                        # tabla completa colapsable
                        with st.expander("Ver detalle completo (tabla)", expanded=False):
                            st.dataframe(resumen, use_container_width=True, hide_index=True)

        st.divider()

    # ---------------------------------------------------------
    # Tabs
    # ---------------------------------------------------------
    def _tab_movimientos(self, df_view):
        with st.container(border=True):
            st.markdown("### 🧾 Movimientos (Histórico)")
            st.caption("Aquí NO se muestran registros cuyo DESTINO sea 'bodega' (esos van solo a la pestaña Bodega).")

            if df_view.empty:
                st.warning("No hay movimientos para mostrar.")
                return

            st.dataframe(df_view.tail(400), use_container_width=True, hide_index=True, height=560)

    def _tab_stock(self, st_res):
        with st.container(border=True):
            st.markdown("### 📦 Stock (Periféricos)")
            if st_res is None or st_res.empty:
                st.info("No hay stock disponible (o no se han registrado periféricos).")
                return

            df = st_res.copy()
            if "cantidad_disponible" in df.columns:
                df["cantidad_disponible"] = pd.to_numeric(df["cantidad_disponible"], errors="coerce").fillna(0).astype(int)
                df = df.sort_values("cantidad_disponible", ascending=False)

            st.dataframe(df, use_container_width=True, hide_index=True, height=560)

    def _tab_bodega(self, bod_res):
        with st.container(border=True):
            st.markdown("### 🏢 Bodega (Cómputo)")
            st.caption("Los registros con DESTINO='bodega' aparecen aquí (aunque también existan en el histórico).")

            if bod_res is None or bod_res.empty:
                st.info("No hay registros que caigan en Bodega.")
                return

            st.dataframe(bod_res, use_container_width=True, hide_index=True, height=560)

    def _tab_danados(self, danados_res):
        with st.container(border=True):
            st.markdown("### 🧯 Dañados / Chatarras / Bajas")
            if danados_res is None or danados_res.empty:
                st.info("No hay registros marcados como dañados/chatarras/bajas.")
                return
            st.dataframe(danados_res, use_container_width=True, hide_index=True, height=560)

    # ---------------------------------------------------------
    # Export
    # ---------------------------------------------------------
    def _crear_boton_descarga(self, st_res, bod_res, danados_res, df_h):
        with st.container(border=True):
            c1, c2 = st.columns([3, 1.4], vertical_alignment="center")
            with c1:
                st.markdown("### 📥 Exportación Excel")
                st.caption("Descarga el Excel con 4 hojas: MOVIMIENTOS, STOCK_SALDOS, BODEGA, DANADOS_CHATARRA.")
            with c2:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                    pd.DataFrame(df_h).to_excel(writer, index=False, sheet_name="MOVIMIENTOS")

                    if isinstance(st_res, pd.DataFrame) and not st_res.empty:
                        st_res.to_excel(writer, index=False, sheet_name="STOCK_SALDOS")
                    else:
                        pd.DataFrame(columns=["equipo", "marca", "val"]).to_excel(writer, index=False, sheet_name="STOCK_SALDOS")

                    if isinstance(bod_res, pd.DataFrame) and not bod_res.empty:
                        bod_res.to_excel(writer, index=False, sheet_name="BODEGA")
                    else:
                        pd.DataFrame().to_excel(writer, index=False, sheet_name="BODEGA")

                    if isinstance(danados_res, pd.DataFrame) and not danados_res.empty:
                        danados_res.to_excel(writer, index=False, sheet_name="DANADOS_CHATARRA")
                    else:
                        pd.DataFrame().to_excel(writer, index=False, sheet_name="DANADOS_CHATARRA")

                timestamp = datetime.datetime.now().strftime("%d_%m_%H%M")
                st.download_button(
                    label="📥 Descargar Excel (4 hojas)",
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

        # compat: si viene fecha_llegada
        if "fecha_llegada" in df.columns and "fecha_registro" not in df.columns:
            df["fecha_registro"] = df["fecha_llegada"]

        # ordenar y formatear fecha
        if "fecha_registro" in df.columns:
            df["fecha_registro"] = pd.to_datetime(df["fecha_registro"], errors="coerce")
            df = df.sort_values("fecha_registro", ascending=True)
            df["fecha_registro"] = df["fecha_registro"].dt.strftime("%Y-%m-%d %H:%M")

        # asegurar columnas típicas
        for c in ["tipo", "equipo", "marca", "modelo", "serie", "estado", "origen", "destino", "reporte", "cantidad", "categoria_item"]:
            if c not in df.columns:
                df[c] = ""

        # cantidad como int (solo UI)
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

        # compat: valor_final -> val
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

        return df.fillna("")

    def _movimientos_sin_destino_bodega(self, df_view):
        """
        Regla JAHER:
        - Si DESTINO == 'bodega' => NO se muestra en Movimientos (solo en Bodega)
        - Si ORIGEN == 'bodega' => se mantiene en Movimientos (normal)
        """
        if df_view is None or df_view.empty:
            return df_view

        if "destino" not in df_view.columns:
            return df_view

        df = df_view.copy()
        dest = df["destino"].astype(str).str.strip().str.lower()

        # filtrar solo los que NO van a bodega como destino
        df = df[dest != "bodega"]

        return df
