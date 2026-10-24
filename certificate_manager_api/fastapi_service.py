# =============================================================================
# fastapi_service.py — Windows Service wrapper for FastAPI
# =============================================================================
#
# Install / update and start the service: run install_service.bat (asks for
# Administrator). Manual commands (Command Prompt as Administrator):
#   python fastapi_service.py --startup auto install
#   python fastapi_service.py start | stop | remove
#
# Settings come from server_settings.json next to this file:
#   {"port": 2030, "https": false}
#   https=true -> uvicorn uses certs\server.crt + certs\server.key
#   (switch with switch_server_mode.bat https|http)
# Server output goes to logs\api_service.log (this folder).
# =============================================================================

import json
import os
import subprocess
import sys

import servicemanager
import win32event
import win32service
import win32serviceutil

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(SERVER_DIR, "server_settings.json")
DEFAULT_SETTINGS = {"port": 2030, "https": False}


def load_settings() -> dict:
    """Read server_settings.json (missing file or keys fall back to port 2030, HTTP)."""
    settings = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, dict):
            settings.update({k: data[k] for k in DEFAULT_SETTINGS if k in data})
    except FileNotFoundError:
        pass
    settings["port"] = int(settings["port"])
    settings["https"] = bool(settings["https"])
    return settings


def python_executable() -> str:
    """python.exe of the installation this service runs under (works for pythonservice.exe too)."""
    candidate = os.path.join(sys.exec_prefix, "python.exe")
    return candidate if os.path.exists(candidate) else sys.executable


def build_uvicorn_command(settings: dict) -> list:
    """Command line that starts the API with the configured port and HTTP/HTTPS mode."""
    cmd = [python_executable(), "-m", "uvicorn", "main:app",
           "--host", "0.0.0.0", "--port", str(settings["port"]), "--timeout-keep-alive", "30"]
    if settings["https"]:
        cert = os.path.join(SERVER_DIR, "certs", "server.crt")
        key = os.path.join(SERVER_DIR, "certs", "server.key")
        if not (os.path.exists(cert) and os.path.exists(key)):
            raise FileNotFoundError("HTTPS is on but certs\\server.crt / server.key are missing. Run setup_server_https.bat.")
        cmd += ["--ssl-certfile", cert, "--ssl-keyfile", key]
    return cmd


class FastAPIWindowsService(win32serviceutil.ServiceFramework):
    _svc_name_ = "FastAPICertificateManager"
    _svc_display_name_ = "FastAPI Certificate Manager Service"
    _svc_description_ = "Background FastAPI Uvicorn service for the Certificate Manager application."

    # Establish a dependency on the apache24 service
    _svc_deps_ = ["apache24"]

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.process = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.main()

    def main(self):
        log_dir = os.path.join(SERVER_DIR, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = open(os.path.join(log_dir, "api_service.log"), "a", encoding="utf-8", buffering=1)
        try:
            settings = load_settings()
            cmd = build_uvicorn_command(settings)
            mode = "HTTPS" if settings["https"] else "HTTP"
            log_file.write(f"\n===== service start: {mode} on port {settings['port']} =====\n")
            servicemanager.LogInfoMsg(f"{self._svc_name_}: starting API ({mode}, port {settings['port']})")

            # Start the FastAPI server using Uvicorn; its output goes to logs\api_service.log
            self.process = subprocess.Popen(
                cmd, cwd=SERVER_DIR, stdout=log_file, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )

            # Wait for the stop signal; if uvicorn dies on its own (e.g. port busy), end the
            # service with an error so Windows shows it stopped and its recovery settings restart it
            while win32event.WaitForSingleObject(self.hWaitStop, 5000) != win32event.WAIT_OBJECT_0:
                if self.process.poll() is not None:
                    raise RuntimeError(f"uvicorn exited with code {self.process.returncode}; see logs\\api_service.log")
        except Exception as exc:
            log_file.write(f"[service error] {exc}\n")
            servicemanager.LogErrorMsg(f"{self._svc_name_}: {exc}")
            failed = True
        else:
            failed = False
        finally:
            # Stop only the uvicorn process this service started
            if self.process is not None:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=5)
                except Exception:
                    try:
                        self.process.kill()
                    except Exception:
                        pass
            log_file.write("===== service stopped =====\n")
            log_file.close()
        if failed:
            # Non-zero exit marks a failure, which triggers the service recovery (auto restart)
            sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(FastAPIWindowsService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(FastAPIWindowsService)
