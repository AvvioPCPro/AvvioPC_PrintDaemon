import sys
import time
import requests
import os
import subprocess
import win32print
import win32api
import json
import threading
import logging
from datetime import datetime
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw

# ==============================================================================
# 1. DAEMON CONFIGURATION & PATHS (PYINSTALLER READY)
# ==============================================================================
# Determine runtime environment (compiled executable vs raw python script)
if getattr(sys, 'frozen', False):
    APPLICATION_PATH = os.path.dirname(sys.executable)
    BUNDLE_DIR = sys._MEIPASS # PyInstaller temporary extraction folder
else:
    APPLICATION_PATH = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = APPLICATION_PATH

GAS_URL = "https://script.google.com/macros/s/AKfycbwHRtrEUUpyIS3vjU3pB1wA57X25FNsrr2xaX2K1Jp2z5PvhGf1D_euM2kPSAIFCCs/exec"
POLLING_INTERVAL = 30  

# Dynamic paths targeting the executable's directory
CONFIG_FILE = os.path.join(APPLICATION_PATH, "config.json")
TEMP_PRINT_FILE = os.path.join(APPLICATION_PATH, "print_in_progress.html")
EDGE_PROFILE_DIR = os.path.join(APPLICATION_PATH, "edge_headless_profile")
LOG_FILE = os.path.join(APPLICATION_PATH, "daemon.log")

# Embedded binary path (SumatraPDF runs from the temp _MEIPASS folder)
SUMATRA_PATH = os.path.join(BUNDLE_DIR, "SumatraPDF.exe")

EDGE_PATH = os.path.join(
    os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"), 
    r"Microsoft\Edge\Application\msedge.exe"
)

# ==============================================================================
# 2. GLOBAL STATE & UNIFIED CONFIGURATION
# ==============================================================================
IS_RUNNING = True
IS_PAUSED = False

config_data = {
    "store_id": "000",
    "target_printer": "",
    "debug_mode": False
}

if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r") as f:
            loaded_data = json.load(f)
            config_data.update(loaded_data)
    except Exception:
        pass
else:
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=4)

STORE_ID = str(config_data.get("store_id", "000")).strip()
TARGET_PRINTER = str(config_data.get("target_printer", "")).strip()
DEBUG_MODE = bool(config_data.get("debug_mode", False))

# ==============================================================================
# 3. LOGGING ENGINE SETUP
# ==============================================================================
log_level = logging.DEBUG if DEBUG_MODE else logging.INFO

logging.basicConfig(
    filename=LOG_FILE,
    level=log_level,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logging.info("=== DAEMON INITIALIZED ===")
logging.info(f"Store ID: {STORE_ID} | Target Printer: {TARGET_PRINTER} | Debug Mode: {DEBUG_MODE}")

# ==============================================================================
# 4. PRINT ENGINE ROUTINE
# ==============================================================================
def print_job(job_data):
    """Generates PDF via Edge and dispatches to spooler silently via SumatraPDF."""
    global TARGET_PRINTER
    
    pc_serial = str(job_data.get('pc_serial', 'UNKNOWN')).strip()
    compiled_html = job_data.get('compiled_html')
    
    if not compiled_html:
        logging.error(f"Missing HTML payload from cloud for S/N: {pc_serial}")
        return
        
    logging.info(f"Processing job for PC S/N: {pc_serial}")
    
    with open(TEMP_PRINT_FILE, "w", encoding="utf-8") as f:
        f.write(compiled_html)
        
    html_abspath = os.path.abspath(TEMP_PRINT_FILE)
    pdf_filename = f"config_{pc_serial}.pdf"
    pdf_abspath = os.path.join(APPLICATION_PATH, pdf_filename)
    
    # Background PDF rendering via Edge
    logging.debug(f"Rendering PDF layout to: {pdf_abspath}")
    cmd_pdf = [
        EDGE_PATH, "--headless", "--disable-gpu", "--log-level=3", 
        "--no-sandbox", f"--user-data-dir={EDGE_PROFILE_DIR}", f"--print-to-pdf={pdf_abspath}", html_abspath
    ]
    
    pdf_process = subprocess.run(cmd_pdf, capture_output=DEBUG_MODE, text=True)
    if DEBUG_MODE and pdf_process.stderr:
        logging.debug(f"Chromium Subsystem Stderr: {pdf_process.stderr.strip()}")
        
    if not os.path.exists(pdf_abspath):
        logging.error(f"PDF generation failed for S/N: {pc_serial}. Target file missing.")
        return
    
    # Spooler routing logic
    try:
        if os.path.exists(SUMATRA_PATH):
            target = TARGET_PRINTER if TARGET_PRINTER else win32print.GetDefaultPrinter()
            logging.info(f"SumatraPDF detected. Routing to target: {target}")
            
            cmd_sumatra = [
                SUMATRA_PATH,
                "-print-to", target,
                "-silent",
                pdf_abspath
            ]
            
            sumatra_process = subprocess.run(cmd_sumatra, capture_output=True, text=True)
            
            if sumatra_process.returncode != 0:
                logging.error(f"SumatraPDF execution failed with exit code: {sumatra_process.returncode}")
                logging.error(f"SumatraPDF Stderr: {sumatra_process.stderr.strip()}")
            else:
                logging.info(f"Print successfully queued in spooler for S/N: {pc_serial}")
            
        else:
            logging.warning("SumatraPDF executable missing. Initiating fallback to system default reader.")
            original_printer = win32print.GetDefaultPrinter()
            if TARGET_PRINTER:
                logging.debug(f"Executing OS default printer hot-swap to: {TARGET_PRINTER}")
                win32print.SetDefaultPrinter(TARGET_PRINTER)

            win32api.ShellExecute(0, "print", pdf_abspath, None, ".", 0)
            time.sleep(8) 
            win32print.SetDefaultPrinter(original_printer)
            logging.info(f"Native print execution triggered for S/N: {pc_serial}")

    except Exception as e:
        logging.critical(f"Spooler transmission failed: {str(e)}", exc_info=True)

    finally:
        try:
            if os.path.exists(pdf_abspath): os.remove(pdf_abspath)
            if os.path.exists(TEMP_PRINT_FILE): os.remove(TEMP_PRINT_FILE)
            logging.debug("Volatile workspace cleanup completed.")
        except Exception as cleanup_error:
            logging.warning(f"Volatile cleanup encountered an issue: {str(cleanup_error)}")

# ==============================================================================
# 5. BACKGROUND DAEMON THREAD
# ==============================================================================
def daemon_loop():
    """Background loop that polls Google Apps Script silently."""
    global IS_RUNNING, IS_PAUSED
    
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
        except Exception as e:
            logging.debug(f"Network polling exception: {e}")

        time.sleep(POLLING_INTERVAL)

# ==============================================================================
# 6. SYSTEM TRAY INTERFACE (UI)
# ==============================================================================
def create_image(width, height):
    """Generates a dynamic Unieuro-colored geometric icon for the tray."""
    image = Image.new('RGB', (width, height), '#003366')
    dc = ImageDraw.Draw(image)
    dc.rectangle((width // 2, 0, width, height // 2), fill='#f37021')
    dc.rectangle((0, height // 2, width // 2, height), fill='#f37021')
    return image

def get_printers():
    """Fetch all local and network printers from Windows."""
    printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
    return [p[2] for p in printers]

def set_printer(icon, query):
    """Save user selected printer to global variable and unified config file."""
    global TARGET_PRINTER, config_data
    TARGET_PRINTER = query.text
    
    config_data["target_printer"] = TARGET_PRINTER
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=4)
        
    logging.info(f"UI Action: Printer changed to {TARGET_PRINTER}")

def toggle_pause(icon, item_val):
    global IS_PAUSED
    IS_PAUSED = not IS_PAUSED
    logging.info(f"UI Action: Daemon Paused state changed to {IS_PAUSED}")

def quit_app(icon, item_val):
    global IS_RUNNING
    IS_RUNNING = False
    logging.info("UI Action: Shutting down daemon...")
    icon.stop()

def build_menu():
    """Constructs the dynamic right-click context menu."""
    printer_items = []
    for p in get_printers():
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
    # Start the main polling engine in an independent background thread
    daemon_thread = threading.Thread(target=daemon_loop, daemon=True)
    daemon_thread.start()

    # Start the System Tray Interface (this locks the main thread)
    icon_image = create_image(64, 64)
    tray_icon = pystray.Icon("AvvioPC", icon_image, "Servizio AvvioPC", build_menu())
    tray_icon.run()