```mermaid
graph TB
    subgraph "INTERFAZ DE USUARIO"
        UI[main.py]
        ChatUI[ui/chat_tab.py]
        StockUI[ui/stock_tab.py]
        CleanUI[ui/cleaning_tab.py]
    end
    
    subgraph "CAPA DE LÓGICA"
        AI[modules/ai_engine.py]
        GH[modules/github_handler.py]
        SC[modules/stock_calculator.py]
        GLPI[modules/glpi_connector.py]
    end
    
    subgraph "CONFIGURACIÓN"
        CFG[config/settings.py]
    end
    
    subgraph "SERVICIOS EXTERNOS"
        OpenAI[OpenAI API]
        GitHub[GitHub Repository]
        GLPIServ[GLPI Server]
    end
    
    UI --> ChatUI
    UI --> StockUI
    UI --> CleanUI
    
    ChatUI --> AI
    ChatUI --> GH
    ChatUI --> SC
    
    StockUI --> GH
    StockUI --> SC
    
    CleanUI --> AI
    CleanUI --> GH
    
    AI --> CFG
    AI --> OpenAI
    
    GH --> CFG
    GH --> GitHub
    
    GLPI --> GH
    GLPI --> GLPIServ
    
    SC --> CFG
    
    style UI fill:#2e7d32,color:#fff
    style AI fill:#1976d2,color:#fff
    style GH fill:#1976d2,color:#fff
    style SC fill:#1976d2,color:#fff
    style GLPI fill:#1976d2,color:#fff
    style CFG fill:#f57c00,color:#fff
    style OpenAI fill:#9c27b0,color:#fff
    style GitHub fill:#9c27b0,color:#fff
    style GLPIServ fill:#9c27b0,color:#fff
```

## Flujo de Datos Principal

```mermaid
sequenceDiagram
    participant U as Usuario
    participant C as ChatUI
    participant A as AI Engine
    participant G as GitHub Handler
    participant R as GitHub Repo
    
    U->>C: Ingresa datos de inventario
    C->>A: Procesa con IA
    A->>A: Valida y estructura
    A-->>C: Retorna JSON estructurado
    C->>G: Solicita guardar
    G->>R: Commit a GitHub
    R-->>G: Confirmación
    G-->>C: Guardado exitoso
    C-->>U: Muestra confirmación
```

## Arquitectura de Capas

```
┌─────────────────────────────────────────────┐
│         PRESENTACIÓN (UI)                   │
│  • Chat Tab                                 │
│  • Stock Tab                                │
│  • Cleaning Tab                             │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│         LÓGICA DE NEGOCIO (Modules)         │
│  • AI Engine (Procesamiento IA)             │
│  • GitHub Handler (Sync)                    │
│  • Stock Calculator (Cálculos)              │
│  • GLPI Connector (Integración)             │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│         CONFIGURACIÓN (Config)              │
│  • Settings                                 │
│  • Prompts                                  │
│  • Credenciales                             │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│         SERVICIOS EXTERNOS                  │
│  • OpenAI API                               │
│  • GitHub Repository                        │
│  • GLPI Server                              │
└─────────────────────────────────────────────┘
```
