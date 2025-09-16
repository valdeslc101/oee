# oee
Streamlit project for managing the OEE indicator in manufacturing lines. It enables recording, visualization, and analysis of production data, times, and downtimes, supporting real-time monitoring and decision-making to improve efficiency and productivity.

# 🏭 Sistema de Monitoreo OEE - Eficiencia General de Equipos

Sistema completo para el cálculo, monitoreo y análisis del OEE (Overall Equipment Effectiveness) con visualización interactiva y reportes automatizados.

## 📊 Características Principales

### 🔢 Cálculo Automático de OEE
- **Disponibilidad**: Tiempo de producción vs tiempo planificado
- **Rendimiento**: Velocidad actual vs velocidad ideal  
- **Calidad**: Unidades buenas vs unidades totales
- **OEE Total**: Disponibilidad × Rendimiento × Calidad

### 📈 Dashboard Interactivo
- **Gráficos en Tiempo Real**: Tendencia OEE por líneas
- **Sankey Diagrams**: Flujo de paros y subparos
- **Métricas KPI**: Visualización de indicadores clave
- **Filtros Dinámicos**: Por fecha, línea, turno

### 🗄️ Gestión de Datos
- **Registro de Paros**: Categorización por causal y subcausal
- **Seguimiento de Producción**: Unidades buenas, defectuosas, velocidad
- **Base de Datos**: Almacenamiento persistente en CSV
- **Actualización Simple**: Interface amigable para captura

## 🚀 Instalación y Configuración

### Prerrequisitos
```bash
Python 3.8+
pip install -r requirements.txt
