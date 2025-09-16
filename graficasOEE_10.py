import numpy as np
import streamlit as st
import pandas as pd
import os
import plotly.graph_objects as go
import csv
import calendar
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# --- Preparación de la base de datos CSV ---
def create_initial_csv_files():
    """
    Crea el archivo CSV de registros si no existe. 
    Asegura que el archivo tenga los encabezados correctos.
    """
    registros_file = 'registros_produccion.csv'
    if not os.path.exists(registros_file):
        with open(registros_file, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            header = ['fecha', 'turno', 'supervisor', 'linea_produccion', 'tiempo_disponible_min',
                      'tiempo_programado_min', 'producto_terminado', 'produccion_real_unidades', 'produccion_defectuosa_unidades',
                      'tiempo_efectivo_min', 'tiempo_no_conformidad_min', 'tiempo_a_justificar_min']
            for i in range(1, 11):
                header.extend([f'paro_causal_{i}', f'paro_subcausal_{i}', f'tiempo_paro_min_{i}'])
            writer.writerow(header)

# Aseguramos que el archivo de registros exista antes de cargar la app
create_initial_csv_files()

def load_data(file_path):
    """Carga los datos desde an archivo CSV."""
    if os.path.exists(file_path):
        return pd.read_csv(file_path)
    return pd.DataFrame()

# --- Configuración de la página ---
st.set_page_config(layout="wide")
st.title("📊 OEE - Efectividad de la Operación")
st.markdown("---")

# --- Cargar datos ---
productos_df = load_data('productos.csv')
registros_df = load_data('registros_produccion.csv')

# Validar que los DataFrames no estén vacíos
if productos_df.empty:
    st.error("Error: Archivo 'productos.csv' no encontrado o vacío.")
    st.stop()
if registros_df.empty:
    st.error("Error: Archivo 'registros_produccion.csv' no encontrado o vacío. Por favor, asegúrese de que el archivo exista y contenga datos.")
    st.stop()

# --- Preprocesamiento de datos para la interfaz ---
registros_df['fecha'] = pd.to_datetime(registros_df['fecha'])
registros_df['mes'] = registros_df['fecha'].dt.month
registros_df['año'] = registros_df['fecha'].dt.year  # Nueva columna para el año

meses_disponibles = sorted(registros_df['mes'].unique())
años_disponibles = sorted(registros_df['año'].unique())  # Lista de años disponibles
lineas_disponibles = sorted(registros_df['linea_produccion'].unique())

# --- Filtros de la interfaz ---
st.sidebar.header("Gráfico Waterfall OEE")

# Selector de año (nuevo)
año_seleccionado = st.sidebar.selectbox(
    "Selecciona el año:",
    años_disponibles
)

mes_seleccionado = st.sidebar.selectbox(
    "Selecciona el mes:",
    meses_disponibles,
    format_func=lambda x: f"{x:02d} - {calendar.month_name[x]}"
)

linea_seleccionada = st.sidebar.selectbox(
    "Selecciona la línea de producción:",
    lineas_disponibles
)

# --- Filtrar los datos ---
df_filtrado = registros_df[
    (registros_df['mes'] == mes_seleccionado) &
    (registros_df['año'] == año_seleccionado) &  # Nuevo filtro por año
    (registros_df['linea_produccion'] == linea_seleccionada)
].copy()

# --- Visualización y Lógica de OEE ---
if df_filtrado.empty:
    st.warning("No hay datos para la selección actual. Por favor, cambia los filtros.")
else:
    # 1. Agregación de métricas de tiempo
    tiempo_disponible = df_filtrado['tiempo_disponible_min'].sum()
    tiempo_programado = df_filtrado['tiempo_programado_min'].sum()
    tiempo_efectivo = df_filtrado['tiempo_efectivo_min'].sum()

    # 2. Consolidación de paros no planificados (EXCLUYENDO Pérdida de velocidad)
    tiempos_paro = {}
    tiempo_perdida_velocidad = 0  # Inicializar el tiempo de pérdida de velocidad
    
    for i in range(1, 11):
        causal = df_filtrado[f'paro_causal_{i}']
        tiempo = df_filtrado[f'tiempo_paro_min_{i}']
        for c, t in zip(causal, tiempo):
            if pd.notna(c) and pd.notna(t):
                # Separar "Pérdida de velocidad" de los demás paros
                if 'pérdida de velocidad' in str(c).lower() or 'perdida de velocidad' in str(c).lower():
                    tiempo_perdida_velocidad += t
                else:
                    tiempos_paro[c] = tiempos_paro.get(c, 0) + t
    
    tiempos_paro_sorted = dict(sorted(tiempos_paro.items(), key=lambda item: item[1], reverse=True))
    
    tiempo_paros_total = sum(tiempos_paro_sorted.values()) + tiempo_perdida_velocidad

    # 3. Cálculo de métricas intermedias
    tiempo_mantenimiento = tiempo_disponible - tiempo_programado
    produccion_real = df_filtrado['produccion_real_unidades'].sum()
    produccion_defectuosa = df_filtrado['produccion_defectuosa_unidades'].sum()
    
    # Cálculo de tiempo de defectos
    tiempo_defectos = (produccion_defectuosa / produccion_real) * tiempo_programado if produccion_real > 0 else 0

    # 4. Construcción del gráfico simulando una cascada con go.Bar
    fig = go.Figure()

    # Función para convertir minutos a días (24 horas de trabajo por día = 1440 minutos)
    def minutos_a_dias(minutos):
        return minutos / 1440  # 24 horas * 60 minutos = 1440 minutos

    # 4.1. Primera barra: Tiempo Disponible (azul)
    fig.add_trace(go.Bar(
        x=['Tiempo Disponible'],
        y=[tiempo_disponible / 60],
        marker_color='blue',
        marker_line=dict(color='black', width=1),
        name='Disponible',
        text=[f"{tiempo_disponible / 60:.0f}h<br>({minutos_a_dias(tiempo_disponible):.1f}d)"],
        textposition='outside',
        textfont=dict(size=14, color='black')
    ))

    # 4.2. Segunda barra: Tiempo Mantenimiento (gris)
    fig.add_trace(go.Bar(
        x=['Tiempo Mantenimiento'],
        y=[-tiempo_mantenimiento / 60],
        base=[tiempo_disponible / 60],
        marker_color='gray',
        marker_line=dict(color='black', width=1),
        name='Mtto. Programado / Detenida',
        text=[f"-{tiempo_mantenimiento / 60:.0f}h<br>({minutos_a_dias(tiempo_mantenimiento):.1f}d)"],
        textposition='outside',
        textfont=dict(size=14, color='black')
    ))
    
    # 4.3. Tercera barra: Tiempo Programado (azul claro)
    fig.add_trace(go.Bar(
        x=['Tiempo Programado'],
        y=[tiempo_programado / 60],
        base=[0],
        marker_color='lightblue',
        marker_line=dict(color='black', width=1),
        name='Programado',
        text=[f"{tiempo_programado / 60:.0f}h<br>({minutos_a_dias(tiempo_programado):.1f}d)"],
        textposition='outside',
        textfont=dict(size=14, color='black')
    ))

    # 4.4. Barras de Paradas (rojo) - EXCLUYENDO Pérdida de velocidad
    base_actual = tiempo_programado
    for i, (causal, tiempo) in enumerate(tiempos_paro_sorted.items()):
        fig.add_trace(go.Bar(
            x=[causal],
            y=[-tiempo / 60],
            base=[base_actual / 60],
            marker_color='red',
            marker_line=dict(color='black', width=1),
            name=causal,
            text=[f"-{tiempo / 60:.0f}h<br>({minutos_a_dias(tiempo):.1f}d)"],
            textposition='outside',
            textfont=dict(size=12, color='black')            
        ))
        base_actual -= tiempo

    # 4.5. Barra de Pérdida de Velocidad (morado claro) - NUEVA
    # Colocada después de los otros paros pero antes de los defectos
    fig.add_trace(go.Bar(
        x=['Pérdida de velocidad'],
        y=[-tiempo_perdida_velocidad / 60],
        base=[base_actual / 60],
        marker_color='#CBC3E3',  # Morado claro
        marker_line=dict(color='black', width=1),
        name='Pérdida de velocidad',
        text=[f"-{tiempo_perdida_velocidad / 60:.0f}h<br>({minutos_a_dias(tiempo_perdida_velocidad):.1f}d)"],
        textposition='outside',
        textfont=dict(size=14, color='black')
    ))
    base_actual -= tiempo_perdida_velocidad

    # 4.6. Barra de Tiempo Defectos (morado)
    fig.add_trace(go.Bar(
        x=['Tiempo Defectos'],
        y=[-tiempo_defectos / 60],
        base=[base_actual / 60],
        marker_color='purple',
        marker_line=dict(color='black', width=1),
        name='Tiempo Defectos Calidad',
        text=[f"-{tiempo_defectos / 60:.0f}h<br>({minutos_a_dias(tiempo_defectos):.1f}d)"],
        textposition='outside',
        textfont=dict(size=14, color='black')
    ))
    base_actual -= tiempo_defectos

    # 4.7. Última barra: Tiempo Efectivo (verde)
    tiempo_efectivo_final = base_actual
    fig.add_trace(go.Bar(
        x=['Tiempo Efectivo'],
        y=[tiempo_efectivo_final / 60],
        base=[0],
        marker_color='green',
        marker_line=dict(color='black', width=1),
        name='Tiempo Efectivo',
        text=[f"{tiempo_efectivo_final / 60:.0f}h<br>({minutos_a_dias(tiempo_efectivo_final):.1f}d)"],
        textposition='outside',
        textfont=dict(size=14, color='black')
    ))

    # Añadir anotaciones en la parte inferior con el tiempo en días
    annotations = []
    
    # Tiempo Disponible
    annotations.append(dict(
        x='Tiempo Disponible', y=-5,
        xref='x', yref='y',
        text=f"{minutos_a_dias(tiempo_disponible):.1f}d",
        showarrow=False,
        font=dict(size=12, color='black'),
        yshift=-25
    ))
    
    # Tiempo Mantenimiento
    annotations.append(dict(
        x='Tiempo Mantenimiento', y=-5,
        xref='x', yref='y',
        text=f"{minutos_a_dias(tiempo_mantenimiento):.1f}d",
        showarrow=False,
        font=dict(size=12, color='black'),
        yshift=-25
    ))
    
    # Tiempo Programado
    annotations.append(dict(
        x='Tiempo Programado', y=-5,
        xref='x', yref='y',
        text=f"{minutos_a_dias(tiempo_programado):.1f}d",
        showarrow=False,
        font=dict(size=12, color='black'),
        yshift=-25
    ))
    
    # Paradas
    for causal in tiempos_paro_sorted.keys():
        tiempo = tiempos_paro_sorted[causal]
        annotations.append(dict(
            x=causal, y=-5,
            xref='x', yref='y',
            text=f"{minutos_a_dias(tiempo):.1f}d",
            showarrow=False,
            font=dict(size=10, color='black'),
            yshift=-25
        ))
    
    # Pérdida de velocidad
    annotations.append(dict(
        x='Pérdida de velocidad', y=-5,
        xref='x', yref='y',
        text=f"{minutos_a_dias(tiempo_perdida_velocidad):.1f}d",
        showarrow=False,
        font=dict(size=12, color='black'),
        yshift=-25
    ))
    
    # Tiempo Defectos
    annotations.append(dict(
        x='Tiempo Defectos', y=-5,
        xref='x', yref='y',
        text=f"{minutos_a_dias(tiempo_defectos):.1f}d",
        showarrow=False,
        font=dict(size=12, color='black'),
        yshift=-25
    ))
    
    # Tiempo Efectivo
    annotations.append(dict(
        x='Tiempo Efectivo', y=-5,
        xref='x', yref='y',
        text=f"{minutos_a_dias(tiempo_efectivo_final):.1f}d",
        showarrow=False,
        font=dict(size=12, color='black'),
        yshift=-25
    ))

    fig.update_layout(
        title_text=f"Análisis de OEE para la Línea {linea_seleccionada} en {calendar.month_name[mes_seleccionado]} {año_seleccionado}",
        showlegend=True,
        yaxis_title="Tiempo (horas)",
        barmode='overlay',
        yaxis_range=[0, tiempo_disponible / 60 * 1.3],  # Aumentado para espacio de anotaciones
        annotations=annotations,
        height=600  # Altura aumentada para mejor visualización
    )

    st.plotly_chart(fig, use_container_width=True)

    # 5. Mostrar el OEE Neto
    oee_neto = (tiempo_efectivo_final / tiempo_programado) * 100 if tiempo_programado > 0 else 0
    st.markdown(f"### **OEE NETO: {oee_neto:.1f}%**")
    
    # Información adicional
    st.write(f"**Resumen de tiempos:**")
    st.write(f"- Tiempo Disponible: {tiempo_disponible/60:.1f}h ({minutos_a_dias(tiempo_disponible):.1f}d)")
    st.write(f"- Tiempo Programado: {tiempo_programado/60:.1f}h ({minutos_a_dias(tiempo_programado):.1f}d)")
    st.write(f"- Tiempo Pérdida Velocidad: {tiempo_perdida_velocidad/60:.1f}h ({minutos_a_dias(tiempo_perdida_velocidad):.1f}d)")
    st.write(f"- Tiempo Efectivo: {tiempo_efectivo_final/60:.1f}h ({minutos_a_dias(tiempo_efectivo_final):.1f}d)")
    
    if tiempos_paro_sorted:
        st.write(f"**Paros encontrados:** {list(tiempos_paro_sorted.keys())}")





# 6. Gráfica de OEE neto acumulado con comparativa anual
st.markdown("---")
st.markdown("### 📈 Línea de tiempo - OEE Comparativo Anual")

# Calcular OEE para todas las líneas y fechas
registros_df['oee_neto'] = (registros_df['tiempo_efectivo_min'] / registros_df['tiempo_programado_min']) * 100
registros_df['oee_neto'] = registros_df['oee_neto'].fillna(0)

# Convertir fecha a datetime y extraer componentes temporales
registros_df['fecha_dt'] = pd.to_datetime(registros_df['fecha'])
registros_df['año'] = registros_df['fecha_dt'].dt.year
registros_df['mes_num'] = registros_df['fecha_dt'].dt.month
registros_df['dia'] = registros_df['fecha_dt'].dt.day
registros_df['trimestre'] = registros_df['fecha_dt'].dt.quarter
registros_df['semana'] = registros_df['fecha_dt'].dt.isocalendar().week
registros_df['dia_mes'] = registros_df['fecha_dt'].dt.day  # Día del mes (1-31)

# Obtener años disponibles
años_disponibles = sorted(registros_df['año'].unique())

# Selector de líneas con checkboxes
st.sidebar.markdown("---")
st.sidebar.subheader("🔧 Comparativa Anual OEE")

# Selector de año actual
año_actual_seleccionado = st.sidebar.selectbox(
    "Selecciona el año actual:",
    options=años_disponibles,
    index=len(años_disponibles)-1 if años_disponibles else 0,
    key="año_actual_select"
)

# Calcular año anterior
año_anterior_seleccionado = año_actual_seleccionado - 1

# Mostrar año anterior (solo lectura)
st.sidebar.text_input(
    "Año anterior:",
    value=f"{año_anterior_seleccionado}",
    disabled=True,
    key="año_anterior_display"
)

todas_lineas = sorted(registros_df['linea_produccion'].unique())
lineas_seleccionadas = st.sidebar.multiselect(
    "Seleccionar Líneas:",
    options=todas_lineas,
    default=[linea_seleccionada],  # La línea actual por defecto
    key="lineas_oee_comparativo"
)

# Selector de nivel de agregación temporal
nivel_agregacion = st.sidebar.selectbox(
    "Nivel Temporal:",
    options=["Día del Mes", "Semana", "Mes"],
    index=0,  # Día del Mes por defecto
    key="nivel_temporal_comparativo"
)

# Filtrar por líneas seleccionadas y años (actual y anterior)
if not lineas_seleccionadas:
    st.warning("Selecciona al menos una línea para visualizar")
else:
    datos_filtrados = registros_df[
        (registros_df['linea_produccion'].isin(lineas_seleccionadas)) &
        (registros_df['año'].isin([año_anterior_seleccionado, año_actual_seleccionado]))
    ].copy()
    
    # Agrupar según el nivel temporal seleccionado
    if nivel_agregacion == "Día del Mes":
        datos_agrupados = datos_filtrados.groupby(['linea_produccion', 'año', 'dia_mes'])['oee_neto'].mean().reset_index()
        x_col = 'dia_mes'
        x_title = 'Día del Mes'
        hover_template = 'Día: %{x}<br>OEE: %{y:.1f}%<br>Año: %{customdata}<extra></extra>'
        x_range = [1, 31]
        
    elif nivel_agregacion == "Semana":
        datos_agrupados = datos_filtrados.groupby(['linea_produccion', 'año', 'semana'])['oee_neto'].mean().reset_index()
        x_col = 'semana'
        x_title = 'Semana del Año'
        hover_template = 'Semana: %{x}<br>OEE: %{y:.1f}%<br>Año: %{customdata}<extra></extra>'
        x_range = [1, 53]
        
    else:  # Mes
        datos_agrupados = datos_filtrados.groupby(['linea_produccion', 'año', 'mes_num'])['oee_neto'].mean().reset_index()
        x_col = 'mes_num'
        x_title = 'Mes'
        hover_template = 'Mes: %{x}<br>OEE: %{y:.1f}%<br>Año: %{customdata}<extra></extra>'
        x_range = [1, 12]
    
    # Crear gráfica comparativa
    fig_comparativo = go.Figure()
    
    # Colores para los años
    color_anterior = "#A59999"  # Gris para año anterior
    color_actual = "#040405"    # Azul para año actual
    
    for i, linea in enumerate(lineas_seleccionadas):
        # Datos del año anterior
        datos_anterior = datos_agrupados[
            (datos_agrupados['linea_produccion'] == linea) & 
            (datos_agrupados['año'] == año_anterior_seleccionado)
        ]
        
        # Datos del año actual
        datos_actual = datos_agrupados[
            (datos_agrupados['linea_produccion'] == linea) & 
            (datos_agrupados['año'] == año_actual_seleccionado)
        ]
        
        # Añadir serie del año anterior (gris oscuro)
        if not datos_anterior.empty:
            fig_comparativo.add_trace(go.Scatter(
                x=datos_anterior[x_col],
                y=datos_anterior['oee_neto'],
                mode='lines+markers+text',
                name=f'{linea} {año_anterior_seleccionado}',
                line=dict(color=color_anterior, width=1.8),
                marker=dict(size=4, color=color_anterior, symbol='circle'),
                customdata=datos_anterior['año'].astype(str),
                hovertemplate=hover_template,
                legendgroup=linea,
                showlegend=True,
                text=[f'{val:.1f}' for val in datos_anterior['oee_neto']],
                textposition='top center',
                textfont=dict(size=8, color=color_anterior)
            ))
        
        # Añadir serie del año actual (verde)
        if not datos_actual.empty:
            fig_comparativo.add_trace(go.Scatter(
                x=datos_actual[x_col],
                y=datos_actual['oee_neto'],
                mode='lines+markers+text',
                name=f'{linea} {año_actual_seleccionado}',
                line=dict(color=color_actual, width=1.8),
                marker=dict(size=5, color=color_actual, symbol='x'),
                customdata=datos_actual['año'].astype(str),
                hovertemplate=hover_template,
                legendgroup=linea,
                showlegend=True,
                text=[f'{val:.1f}' for val in datos_actual['oee_neto']],
                textposition='bottom center',
                textfont=dict(size=8, color=color_actual)
            ))
    
    # Añadir líneas de referencia
    fig_comparativo.add_trace(go.Scatter(
        x=x_range,
        y=[85.0] * 2,
        mode='lines',
        name='Límite 85%',
        line=dict(color='blue', width=1.0, dash='dash'),
        hovertemplate='Límite: 85.0%<extra></extra>',
        showlegend=True
    ))

    fig_comparativo.add_trace(go.Scatter(
        x=x_range,
        y=[70.0] * 2,
        mode='lines',
        name='Límite Inferior 70%',
        line=dict(color='red', width=1.0, dash='dash'),
        hovertemplate='Límite Inferior: 70.0%<extra></extra>',
        showlegend=True
    ))

    # Añadir zona de tolerancia
    fig_comparativo.add_trace(go.Scatter(
        x=x_range + x_range[::-1],
        y=[70.0] * len(x_range) + [85.0] * len(x_range),
        fill='toself',
        fillcolor='rgba(173, 216, 230, 0.3)',
        line=dict(color='rgba(0,0,0,0)'),
        name='Zona Tolerancia (70-85%)',
        hoverinfo='skip',
        showlegend=True
    ))
    
    # Configurar layout
    fig_comparativo.update_layout(
        title=f'Comparativa OEE {año_anterior_seleccionado} vs {año_actual_seleccionado} - Nivel {nivel_agregacion}',
        xaxis_title=x_title,
        yaxis_title='OEE Neto (%)',
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(family='Arial', size=12),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        height=500,
        xaxis=dict(
            range=x_range,
            gridcolor='lightgray',
            gridwidth=1,
            dtick=1 if nivel_agregacion in ["Día del Mes", "Mes"] else 4
        ),
        yaxis=dict(
            range=[0, 100],
            gridcolor='lightgray',
            gridwidth=1,
            ticksuffix='%'
        )
    )
    
    # Añadir cuadrícula
    fig_comparativo.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
    fig_comparativo.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
    
    # Mostrar estadísticas comparativas
    st.plotly_chart(fig_comparativo, use_container_width=True)
    
    # Estadísticas comparativas
    st.markdown("### 📊 Estadísticas Comparativas")
    
    for linea in lineas_seleccionadas:
        col1, col2, col3 = st.columns(3)
        
        # OEE promedio año anterior
        oee_anterior = datos_agrupados[
            (datos_agrupados['linea_produccion'] == linea) & 
            (datos_agrupados['año'] == año_anterior_seleccionado)
        ]['oee_neto'].mean()
        
        # OEE promedio año actual
        oee_actual_val = datos_agrupados[
            (datos_agrupados['linea_produccion'] == linea) & 
            (datos_agrupados['año'] == año_actual_seleccionado)
        ]['oee_neto'].mean()
        
        with col1:
            if not pd.isna(oee_anterior):
                st.metric(
                    label=f"OEE Promedio {año_anterior_seleccionado} - Línea {linea}",
                    value=f"{oee_anterior:.1f}%",
                    delta=None
                )
        
        with col2:
            if not pd.isna(oee_actual_val):
                st.metric(
                    label=f"OEE Promedio {año_actual_seleccionado} - Línea {linea}",
                    value=f"{oee_actual_val:.1f}%",
                    delta=None
                )
        
        with col3:
            # Variación
            if not pd.isna(oee_anterior) and not pd.isna(oee_actual_val):
                variacion = oee_actual_val - oee_anterior
                st.metric(
                    label=f"Variación - Línea {linea}",
                    value=f"{variacion:+.1f}%",
                    delta=f"{variacion:+.1f}%"
                )


    # 8. Gráfico de Pareto para Subparos
st.markdown("---")
st.markdown("### 📊 Análisis de Pareto para Subparos")

# Preparar datos para el gráfico de Pareto
pareto_df = registros_df.copy()

# Asegurarnos de que tenemos las columnas necesarias
if 'fecha' in pareto_df.columns:
    pareto_df['fecha_dt'] = pd.to_datetime(pareto_df['fecha'])
else:
    st.error("No se encuentra la columna 'fecha' en los datos.")
    st.stop()

# Crear contenedor para los filtros
col_filtro1, col_filtro2, col_filtro3, col_filtro4, col_filtro5, col_filtro6 = st.columns(6)

with col_filtro1:
    pareto_semana_btn = st.button("Última Semana", key="pareto_semana_btn", use_container_width=True)
with col_filtro2:
    pareto_ytd_btn = st.button("YTD", key="pareto_ytd_btn", use_container_width=True)
with col_filtro3:
    pareto_mes_btn = st.button("1 Mes", key="pareto_mes_btn", use_container_width=True)
with col_filtro4:
    pareto_seis_meses_btn = st.button("6 Meses", key="pareto_seis_meses_btn", use_container_width=True)
with col_filtro5:
    pareto_año_btn = st.button("1 Año", key="pareto_año_btn", use_container_width=True)
with col_filtro6:
    pareto_todo_btn = st.button("Todo", key="pareto_todo_btn", use_container_width=True)

# Selector de línea de producción para el gráfico de Pareto
lineas_pareto = sorted(pareto_df['linea_produccion'].unique())
linea_seleccionada_pareto = st.selectbox(
    "Seleccionar Línea de Producción:",
    options=lineas_pareto,
    index=0,
    key="linea_pareto"
)

# Filtrar por línea seleccionada
pareto_df = pareto_df[pareto_df['linea_produccion'] == linea_seleccionada_pareto]

# Determinar el filtro temporal según el botón presionado
hoy = pd.to_datetime('today')
filtro_temporal_pareto = "YTD"  # Valor por defecto

if pareto_semana_btn:
    filtro_temporal_pareto = "Última Semana"
    una_semana_atras = hoy - pd.DateOffset(weeks=1)
    pareto_df = pareto_df[pareto_df['fecha_dt'] >= una_semana_atras]
elif pareto_mes_btn:
    filtro_temporal_pareto = "1 Mes"
    un_mes_atras = hoy - pd.DateOffset(months=1)
    pareto_df = pareto_df[pareto_df['fecha_dt'] >= un_mes_atras]
elif pareto_seis_meses_btn:
    filtro_temporal_pareto = "6 Meses"
    seis_meses_atras = hoy - pd.DateOffset(months=6)
    pareto_df = pareto_df[pareto_df['fecha_dt'] >= seis_meses_atras]
elif pareto_año_btn:
    filtro_temporal_pareto = "1 Año"
    un_año_atras = hoy - pd.DateOffset(years=1)
    pareto_df = pareto_df[pareto_df['fecha_dt'] >= un_año_atras]
elif pareto_todo_btn:
    filtro_temporal_pareto = "Todo"
    # No aplicar filtro
else:
    # YTD por defecto
    filtro_temporal_pareto = "YTD"
    inicio_año = pd.to_datetime(f'{hoy.year}-01-01')
    pareto_df = pareto_df[pareto_df['fecha_dt'] >= inicio_año]

# Extraer todos los subparos y sus tiempos
subparos_data = []
for i in range(1, 11):
    causal_col = f'paro_causal_{i}'
    tiempo_col = f'tiempo_paro_min_{i}'
    
    if causal_col in pareto_df.columns and tiempo_col in pareto_df.columns:
        for index, row in pareto_df.iterrows():
            if pd.notna(row[causal_col]) and pd.notna(row[tiempo_col]) and row[tiempo_col] > 0:
                subparos_data.append({
                    'subparo': row[causal_col],
                    'tiempo_min': row[tiempo_col]
                })

# Crear DataFrame de subparos
if subparos_data:
    subparos_df = pd.DataFrame(subparos_data)
    
    # Agrupar por tipo de subparo y sumar tiempos
    subparos_agrupados = subparos_df.groupby('subparo')['tiempo_min'].sum().reset_index()
    
    # Convertir a horas
    subparos_agrupados['tiempo_hrs'] = subparos_agrupados['tiempo_min'] / 60
    
    # Ordenar de mayor a menor
    subparos_agrupados = subparos_agrupados.sort_values('tiempo_hrs', ascending=False)
    
    # Calcular porcentaje acumulado
    subparos_agrupados['porcentaje_acumulado'] = (subparos_agrupados['tiempo_hrs'].cumsum() / 
                                                 subparos_agrupados['tiempo_hrs'].sum() * 100)
    
    # Identificar los subparos que representan el 80% del tiempo total
    subparos_agrupados['color'] = subparos_agrupados['porcentaje_acumulado'].apply(
        lambda x: 'red' if x <= 80 else 'gray'
    )
    
    # Crear gráfico de Pareto
    fig_pareto = go.Figure()
    
    # Añadir barras con bordes negros
    fig_pareto.add_trace(go.Bar(
        x=subparos_agrupados['subparo'],
        y=subparos_agrupados['tiempo_hrs'],
        marker_color=subparos_agrupados['color'],
        marker_line=dict(color='black', width=1),  # Bordes negros
        name='Tiempo de Subparo (horas)',
        hovertemplate='Subparo: %{x}<br>Tiempo: %{y:.2f} horas<extra></extra>',
        width=0.5,  # Controlar el ancho de las barras
        text=subparos_agrupados['tiempo_hrs'].round(1),  # Etiquetas de valores
        textposition='outside',  # Etiquetas fuera de las barras
        textfont=dict(color='black', size=10)  # Color y tamaño de etiquetas
    ))
    
    # Añadir línea de porcentaje acumulado
    fig_pareto.add_trace(go.Scatter(
        x=subparos_agrupados['subparo'],
        y=subparos_agrupados['porcentaje_acumulado'],
        mode='lines+markers',
        name='% Acumulado',
        yaxis='y2',
        line=dict(color='blue', width=2),
        marker=dict(size=6),
        hovertemplate='Subparo: %{x}<br>% Acumulado: %{y:.1f}%<extra></extra>'
    ))
    
    # Configurar layout
    fig_pareto.update_layout(
        title=f"Análisis de Pareto de Subparos - Línea {linea_seleccionada_pareto} - Período: {filtro_temporal_pareto}",
        xaxis_title="Tipos de Subparo",
        yaxis_title="Tiempo Subparo (horas)",
        yaxis2=dict(
            title="Tiempo Acumulado (%)",
            overlaying='y',
            side='right',
            range=[0, 100],  # Fijar rango del 0% al 100%
            tickvals=[0, 20, 40, 60, 80, 100],
            ticktext=['0%', '20%', '40%', '60%', '80%', '100%']
        ),
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(family='Arial', size=6),
        height=600,
        showlegend=True,
        legend=dict(
            x=1.15,  # Mover leyenda a la derecha
            y=0.7,
            xanchor='left',
            yanchor='top',
            bgcolor='rgba(255, 255, 255, 0.8)',
        ),
        xaxis=dict(
            tickangle=45,
            type='category',  # Asegurar que el eje X sea categórico
            range=[-0.5, len(subparos_agrupados) - 0.5]  # Ajustar rango para que las barras no se salgan
        ),
        yaxis=dict(
            rangemode='nonnegative',  # Asegurar que el eje Y no muestre valores negativos
            zeroline=True,
            zerolinewidth=1,
            zerolinecolor='lightgray'
        ),
        bargap=0.1,  # Espacio entre barras
        bargroupgap=0.1,  # Espacio entre grupos de barras
        margin=dict(r=150)  # Margen derecho para la leyenda
    )
    
    # Configurar ejes para que no se desborden
    fig_pareto.update_xaxes(
        gridcolor='lightgray',
        gridwidth=1,
        showgrid=False  # Ocultar grid vertical para mejor visualización
    )
    
    fig_pareto.update_yaxes(
        gridcolor='lightgray',
        gridwidth=1
    )
    
    # Añadir anotación para explicar los colores
    fig_pareto.add_annotation(
        x=1.35, y=0.35,
        xref="paper", yref="paper",
        text="🔴 Pocos Vitales<br>🔘 Muchos Triviales",
        showarrow=False,
        font=dict(size=10, color="black"),
        bgcolor="rgba(255,255,255,0.8)",
        bordercolor="black",
        borderwidth=0.5
    )
    
    # Añadir línea de referencia al 80%
    fig_pareto.add_hline(y=80, line_dash="dash", line_color="red", 
                        opacity=0.7, yref="y2",
                        annotation_text="80%", 
                        annotation_position="top right")
    
    st.plotly_chart(fig_pareto, use_container_width=True)
    
    # Mostrar estadísticas resumidas
    st.markdown("**📈 Estadísticas de Subparos:**")
    
    total_tiempo_hrs = subparos_agrupados['tiempo_hrs'].sum()
    total_subparos = len(subparos_agrupados)
    subparos_vitales = subparos_agrupados[subparos_agrupados['color'] == 'red']
    num_vitales = len(subparos_vitales)
    tiempo_vitales = subparos_vitales['tiempo_hrs'].sum()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Tiempo Subparos", f"{total_tiempo_hrs:.1f} horas")
    with col2:
        st.metric("Total Tipos de Subparos", f"{total_subparos}")
    with col3:
        st.metric("Subparos Vitales (80/20)", f"{num_vitales}")
    with col4:
        st.metric("Tiempo Subparos Vitales", f"{tiempo_vitales:.1f} horas")
    
    # Mostrar tabla con detalles
    st.markdown("**📋 Detalle de Subparos:**")
    subparos_detalle = subparos_agrupados[['subparo', 'tiempo_hrs', 'porcentaje_acumulado']].copy()
    subparos_detalle['tiempo_hrs'] = subparos_detalle['tiempo_hrs'].round(2)
    subparos_detalle['porcentaje_acumulado'] = subparos_detalle['porcentaje_acumulado'].round(1)
    subparos_detalle.columns = ['Tipo de Subparo', 'Tiempo (horas)', '% Acumulado']
    
    st.dataframe(subparos_detalle, use_container_width=True, hide_index=True)
    
else:
    st.warning(f"No se encontraron datos de subparos para la línea {linea_seleccionada_pareto} en el período seleccionado.")







# 9. Mini Histogramas de Distribución por Línea
st.markdown("---")
st.markdown("### 📊 Mini Histogramas - Distribución por Línea")

# Filtros para los mini histogramas
st.sidebar.markdown("---")
st.sidebar.subheader("🔧 Filtros Mini Histogramas")

# Selector de período temporal
periodo_hist = st.sidebar.selectbox(
    "Período temporal:",
    options=["YTD", "Último mes", "Último 6 meses", "Último año"],
    index=0,
    key="periodo_hist"
)

# Obtener fecha actual y calcular fechas de filtro
fecha_actual = datetime.now()
df_hist = registros_df.copy()

if periodo_hist == "YTD":
    # Year to date (desde inicio del año actual)
    df_hist = df_hist[df_hist['año'] == fecha_actual.year]
    titulo_periodo = f"YTD {fecha_actual.year}"
    
elif periodo_hist == "Último mes":
    # Último mes completo
    primer_dia_mes_anterior = (fecha_actual.replace(day=1) - timedelta(days=1)).replace(day=1)
    df_hist = df_hist[
        (df_hist['año'] == primer_dia_mes_anterior.year) & 
        (df_hist['mes_num'] == primer_dia_mes_anterior.month)
    ]
    titulo_periodo = f"{calendar.month_name[primer_dia_mes_anterior.month]} {primer_dia_mes_anterior.year}"
    
elif periodo_hist == "Último 6 meses":
    # Últimos 6 meses completos
    seis_meses_atras = fecha_actual - relativedelta(months=6)
    df_hist = df_hist[
        (df_hist['fecha'] >= seis_meses_atras.replace(day=1)) &
        (df_hist['fecha'] <= fecha_actual)
    ]
    titulo_periodo = "Últimos 6 meses"
    
elif periodo_hist == "Último año":
    # Último año completo
    df_hist = df_hist[df_hist['año'] == fecha_actual.year - 1]
    titulo_periodo = f"Año {fecha_actual.year - 1}"

if df_hist.empty:
    st.warning(f"No hay datos disponibles para el período: {periodo_hist}.")
else:
    if 'produccion_real_unidades' not in df_hist.columns:
        st.error("La columna 'produccion_real_unidades' no existe.")
    else:
        # Obtener líneas únicas
        lineas_unicas = sorted(df_hist['linea_produccion'].dropna().unique())
        
        if not lineas_unicas:
            st.warning("No hay datos de líneas de producción para el período seleccionado.")
        else:
            # Calcular número de columnas (máximo 4 por fila)
            n_lineas = len(lineas_unicas)
            n_cols = min(4, n_lineas)
            n_rows = (n_lineas + n_cols - 1) // n_cols
            
            # Importar make_subplots
            from plotly.subplots import make_subplots
            
            # Crear subplots
            fig = make_subplots(
                rows=n_rows, 
                cols=n_cols,
                subplot_titles=lineas_unicas,
                horizontal_spacing=0.05,
                vertical_spacing=0.1
            )
            
            # Colores minimalistas
            color_barras = "#030585"  # Gris azulado oscuro
            color_media = "#111111"   # Rojo
            color_mediana = "#F7F8FA" # Azul oscuro
            
            # Crear un histograma por línea
            for i, linea in enumerate(lineas_unicas):
                row = (i // n_cols) + 1
                col = (i % n_cols) + 1
                
                # Filtrar datos de la línea
                data_linea = df_hist[df_hist['linea_produccion'] == linea]['produccion_real_unidades']
                
                if not data_linea.empty and data_linea.notna().any():
                    # Calcular estadísticas
                    media = data_linea.mean()
                    mediana = data_linea.median()
                    
                    # Crear histograma con pocos bins
                    hist_data = data_linea.dropna()
                    if len(hist_data) > 0:
                        # Crear histograma
                        fig.add_trace(
                            go.Histogram(
                                x=hist_data,
                                nbinsx=15,  # Pocos bins para mini histogramas
                                name=linea,
                                marker_color=color_barras,
                                opacity=0.8,
                                showlegend=False,
                                hovertemplate=f'Línea: {linea}<br>Producción: %{{x:,.0f}}<br>Frecuencia: %{{y}}<extra></extra>'
                            ),
                            row=row, col=col
                        )
                        
                        # Añadir línea de media
                        y_max = hist_data.value_counts().max() * 1.1 if len(hist_data.value_counts()) > 0 else 1
                        fig.add_trace(
                            go.Scatter(
                                x=[media, media],
                                y=[0, y_max],
                                mode='lines',
                                line=dict(color=color_media, width=1.5, dash='dash'),
                                name='Media',
                                showlegend=False,
                                hovertemplate=f'Media: {media:,.0f}<extra></extra>'
                            ),
                            row=row, col=col
                        )
                        
                        # Añadir línea de mediana
                        fig.add_trace(
                            go.Scatter(
                                x=[mediana, mediana],
                                y=[0, y_max],
                                mode='lines',
                                line=dict(color=color_mediana, width=1.5, dash='dot'),
                                name='Mediana',
                                showlegend=False,
                                hovertemplate=f'Mediana: {mediana:,.0f}<extra></extra>'
                            ),
                            row=row, col=col
                        )
            
            # Configurar layout ultra minimalista
            fig.update_layout(
                title=f"Distribución de Producción - {titulo_periodo}",
                height=150 * n_rows,  # Altura dinámica
                showlegend=False,
                plot_bgcolor='white',
                paper_bgcolor='white',
                font=dict(size=9),
                margin=dict(l=20, r=20, t=60, b=20)
            )
            
            # Configurar ejes minimalistas
            fig.update_xaxes(
                showgrid=False,
                showticklabels=True,
                tickfont=dict(size=10,color='#000000'),
                title_font=dict(size=8)
            )
            
            fig.update_yaxes(
                showgrid=False,
                showticklabels=False,
                title_text=''
            )
            
            # Ajustar títulos de subplots
            fig.update_annotations(font_size=20)
            
            st.plotly_chart(fig, use_container_width=True)
            