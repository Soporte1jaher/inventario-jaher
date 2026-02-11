"""
verify_install.py
Script para verificar que todos los módulos estén instalados correctamente
"""
import sys

def verificar_estructura():
    """Verifica que todos los archivos existan"""
    import os
    
    archivos_requeridos = [
        'main.py',
        'config/__init__.py',
        'config/settings.py',
        'modules/__init__.py',
        'modules/github_handler.py',
        'modules/ai_engine.py',
        'modules/stock_calculator.py',
        'modules/glpi_connector.py',
        'ui/__init__.py',
        'ui/chat_tab.py',
        'ui/stock_tab.py',
        'ui/cleaning_tab.py',
        'requirements.txt',
        'README.md'
    ]
    
    print("🔍 Verificando estructura de archivos...")
    faltantes = []
    
    for archivo in archivos_requeridos:
        if os.path.exists(archivo):
            print(f"  ✅ {archivo}")
        else:
            print(f"  ❌ {archivo} - FALTANTE")
            faltantes.append(archivo)
    
    if faltantes:
        print(f"\n⚠️  ADVERTENCIA: {len(faltantes)} archivos faltantes")
        return False
    else:
        print("\n✅ Todos los archivos están presentes")
        return True

def verificar_dependencias():
    """Verifica que todas las librerías estén instaladas"""
    print("\n🔍 Verificando dependencias...")
    
    dependencias = [
        ('streamlit', 'streamlit'),
        ('openai', 'openai'),
        ('pandas', 'pandas'),
        ('requests', 'requests'),
        ('xlsxwriter', 'xlsxwriter')
    ]
    
    faltantes = []
    
    for nombre, paquete in dependencias:
        try:
            __import__(paquete)
            print(f"  ✅ {nombre}")
        except ImportError:
            print(f"  ❌ {nombre} - NO INSTALADO")
            faltantes.append(nombre)
    
    if faltantes:
        print(f"\n⚠️  ADVERTENCIA: {len(faltantes)} dependencias faltantes")
        print("\nPara instalar, ejecuta:")
        print("  pip install -r requirements.txt")
        return False
    else:
        print("\n✅ Todas las dependencias están instaladas")
        return True

def verificar_imports():
    """Verifica que los imports funcionen correctamente"""
    print("\n🔍 Verificando imports...")
    
    imports = [
        ('config.settings', 'Config'),
        ('modules.github_handler', 'GitHubHandler'),
        ('modules.ai_engine', 'AIEngine'),
        ('modules.stock_calculator', 'StockCalculator'),
        ('modules.glpi_connector', 'GLPIConnector'),
        ('ui.chat_tab', 'ChatTab'),
        ('ui.stock_tab', 'StockTab'),
        ('ui.cleaning_tab', 'CleaningTab')
    ]
    
    errores = []
    
    for modulo, clase in imports:
        try:
            mod = __import__(modulo, fromlist=[clase])
            getattr(mod, clase)
            print(f"  ✅ {modulo}.{clase}")
        except Exception as e:
            print(f"  ❌ {modulo}.{clase} - ERROR: {str(e)}")
            errores.append(f"{modulo}.{clase}")
    
    if errores:
        print(f"\n⚠️  ADVERTENCIA: {len(errores)} imports fallidos")
        return False
    else:
        print("\n✅ Todos los imports funcionan correctamente")
        return True

def main():
    """Función principal"""
    print("="*60)
    print("  VERIFICADOR DE INSTALACIÓN - LAIA v91.2")
    print("="*60)
    
    estructura_ok = verificar_estructura()
    dependencias_ok = verificar_dependencias()
    imports_ok = verificar_imports()
    
    print("\n" + "="*60)
    print("  RESUMEN")
    print("="*60)
    
    if estructura_ok and dependencias_ok and imports_ok:
        print("\n✅ ¡TODO ESTÁ LISTO!")
        print("\nPara ejecutar la aplicación:")
        print("  streamlit run main.py")
        print("\n")
        return 0
    else:
        print("\n❌ HAY PROBLEMAS QUE RESOLVER")
        print("\nRevisa los errores arriba y corrígelos antes de continuar.")
        print("\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
