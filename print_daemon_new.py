import sys
import time
import requests
import os
import subprocess
import win32print
import win32api
import json
import threading
from datetime import datetime
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw

# ==============================================================================
# DAEMON CONFIGURATION & PATHS (PYINSTALLER READY)
# ==============================================================================
# Determine if application is a script file or frozen exe
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    APPLICATION_PATH = os.path.dirname(sys.executable)
    BUNDLE_DIR = sys._MEIPASS
else:
    # Running as standard Python script
    APPLICATION_PATH = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = APPLICATION_PATH

GAS_URL = "https://script.google.com/macros/s/AKfycbwHRtrEUUpyIS3vjU3pB1wA57X25FNsrr2xaX2K1Jp2z5PvhGf1D_euM2kPSAIFCCs/exec"
POLLING_INTERVAL = 30  

# External assets (Must reside in the actual executable folder)
CONFIG_FILE = os.path.join(APPLICATION_PATH, "config.json")
TEMP_PRINT_FILE = os.path.join(APPLICATION_PATH, "print_in_progress.html")
EDGE_PROFILE_DIR = os.path.join(APPLICATION_PATH, "edge_headless_profile")

# Embedded assets (Extracted to temporary folder by PyInstaller)
SUMATRA_PATH = os.path.join(BUNDLE_DIR, "SumatraPDF.exe")

EDGE_PATH = os.path.join(
    os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"), 
    r"Microsoft\Edge\Application\msedge.exe"
)

# ==============================================================================
# GLOBAL STATE & UNIFIED CONFIGURATION
# ==============================================================================
IS_RUNNING = True
IS_PAUSED = False

# Default dictionary setup
config_data = {
    "store_id": "000",
    "target_printer": ""
}

# Unified configuration initialization
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r") as f:
            loaded_data = json.load(f)
            config_data.update(loaded_data)
    except Exception as e:
        print(f"[WARNING] Config read error, applying defaults: {e}")
else:
    # Generate new config file if absent
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=4)

STORE_ID = str(config_data["store_id"]).strip()
TARGET_PRINTER = str(config_data["target_printer"]).strip()

# ==============================================================================
# PRINT ENGINE ROUTINE
# ==============================================================================
def print_job(job_data):
    """Generates PDF via Edge and dispatches to spooler silently via SumatraPDF."""
    global TARGET_PRINTER
    
    pc_serial = str(job_data.get('pc_serial', 'UNKNOWN')).strip()
    compiled_html = job_data.get('compiled_html')
    
    if not compiled_html:
        return
        
    print(f"-> Processing job for PC S/N: {pc_serial}")
    
    with open(TEMP_PRINT_FILE, "w", encoding="utf-8") as f:
        f.write(compiled_html)
        
    html_abspath = os.path.abspath(TEMP_PRINT_FILE)
    pdf_filename = f"config_{pc_serial}.pdf"
    pdf_abspath = os.path.join(APPLICATION_PATH, pdf_filename)
    
    # 1. Background PDF rendering via Edge
    cmd_pdf = [
        EDGE_PATH, "--headless", "--disable-gpu", "--log-level=3", 
        "--no-sandbox", f"--user-data-dir={EDGE_PROFILE_DIR}", f"--print-to-pdf={pdf_abspath}", html_abspath
    ]
    subprocess.run(cmd_pdf, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # 2. Spooler routing logic
    try:
        if os.path.exists(SUMATRA_PATH):
            # STEALTH MODE (Direct routing, no UI)
            print("   [INFO] SumatraPDF detected. Executing stealth print...")
            target = TARGET_PRINTER if TARGET_PRINTER else win32print.GetDefaultPrinter()
            
            cmd_sumatra = [
                SUMATRA_PATH,
                "-print-to", target,
                "-silent",
                pdf_abspath
            ]
            subprocess.run(cmd_sumatra, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"   [OK] Print successfully routed for S/N: {pc_serial}\n")
            
        else:
            # NATIVE FALLBACK (System reader, potential popups)
            print("   [WARNING] SumatraPDF missing. Fallback to system default reader.")
            original_printer = win32print.GetDefaultPrinter()
            if TARGET_PRINTER:
                win32print.SetDefaultPrinter(TARGET_PRINTER)

            win32api.ShellExecute(0, "print", pdf_abspath, None, ".", 0)
            time.sleep(8) 
            win32print.SetDefaultPrinter(original_printer)
            print(f"   [OK] Print successfully routed for S/N: {pc_serial}\n")

    except Exception as e:
        print(f"   [CRITICAL] Spooler transmission failed: {e}")

    finally:
        # Volatile assets cleanup
        try:
            if os.path.exists(pdf_abspath): os.remove(pdf_abspath)
            if os.path.exists(TEMP_PRINT_FILE): os.remove(TEMP_PRINT_FILE)
        except:
            pass

# ==============================================================================
# BACKGROUND DAEMON THREAD
# ==============================================================================
def daemon_loop():
    """Background loop that polls Google Apps Script silently."""
    global IS_RUNNING, IS_PAUSED
    
    print("=========================================================")
    print(f" AVVIOPC PRINT DAEMON WORKING IN BACKGROUND")
    print(f" Store ID: {STORE_ID} | Active Printer: {TARGET_PRINTER or 'OS Default'}")
    print("=========================================================\n")

    while IS_RUNNING:
        if IS_PAUSED:
            time.sleep(2)
            continue

        try:
            response = requests.get(f"{GAS_URL}?action=get_print_jobs&store_id={STORE_ID}", timeout=15)
            result = response.json()

            if result.get("status") == "success":
                jobs = result.get("data", [])
                if jobs:
                    for job in jobs:
                        print_job(job)
                        time.sleep(2)
        except Exception:
            pass # Silent failure on network drops

        time.sleep(POLLING_INTERVAL)

# ==============================================================================
# SYSTEM TRAY INTERFACE (UI)
# ==============================================================================
def create_image(width, height):
    """Generates a dynamic Unieuro-colored geometric icon for the tray."""
    image = Image.new('RGB', (width, height), '#003366') # Blue
    dc = ImageDraw.Draw(image)
    dc.rectangle((width // 2, 0, width, height // 2), fill='#f37021') # Orange
    dc.rectangle((0, height // 2, width // 2, height), fill='#f37021') # Orange
    return image

def get_printers():
    """Fetch all local and network printers from Windows."""
    printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
    return [p[2] for p in printers]

def set_printer(icon, query):
    """Save user selected printer to global variable and unified config file."""
    global TARGET_PRINTER, config_data
    TARGET_PRINTER = query.text
    
    # Aggiorna il dizionario in memoria e lo salva sul file unificato
    config_data["target_printer"] = TARGET_PRINTER
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=4)
        
    print(f"[UI] Stampante impostata su: {TARGET_PRINTER}")

def toggle_pause(icon, item_val):
    global IS_PAUSED
    IS_PAUSED = not IS_PAUSED
    print(f"[UI] Daemon Paused: {IS_PAUSED}")

def quit_app(icon, item_val):
    global IS_RUNNING
    IS_RUNNING = False
    print("[UI] Shutting down daemon...")
    icon.stop()

def build_menu():
    """Constructs the dynamic right-click context menu."""
    printer_items = []
    for p in get_printers():
        # Add a checkmark next to the currently active printer
        printer_items.append(item(p, set_printer, checked=lambda i, p_name=p: TARGET_PRINTER == p_name))

    return pystray.Menu(
        item('AvvioPC Print Daemon', lambda: None, enabled=False),
        pystray.Menu.SEPARATOR,
        item('Seleziona Stampante', pystray.Menu(*printer_items)),
        pystray.Menu.SEPARATOR,
        item(lambda text: '▶ Riprendi Servizio' if IS_PAUSED else '⏸ Sospendi Servizio', toggle_pause),
        item('✖ Esci', quit_app)
    )

if __name__ == "__main__":
    # 1. Start the main polling engine in an independent background thread
    daemon_thread = threading.Thread(target=daemon_loop, daemon=True)
    daemon_thread.start()

    # 2. Start the System Tray Interface (this locks the main thread)
    icon_image = create_image(64, 64)
    tray_icon = pystray.Icon("AvvioPC", icon_image, "Servizio AvvioPC", build_menu())
    tray_icon.run()