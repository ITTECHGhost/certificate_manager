# =============================================================================
# regweb_service.py — Windows service "RegWebRegistration" for registration_web
# =============================================================================
# Same pattern as certificate_manager_api/fastapi_service.py (pywin32, already on
# the server). Installed by install_service.ps1; runs under the SYSTEM python and
# starts waitress with the venv python (.venv\Scripts\python.exe).
#
# Reads service_config.json next to this file (written by the installer, not in git):
#   {"data_dir": "C:\\registration_data"}
# Port and allowed hosts come from <data_dir>\settings.json. Log: <data_dir>\logs\service.log
# Start / stop: services.msc -> "Registration Web (التسجيل)", or regweb_start.bat / regweb_stop.bat
# Independent of Apache (AppServ or WAMP): waitress listens on its own port.
# =============================================================================
import json
import os
import subprocess
import sys

import servicemanager
import win32event
import win32service
import win32serviceutil

APP_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(APP_DIR, ".venv", "Scripts", "python.exe")


def load_config():
    with open(os.path.join(APP_DIR, "service_config.json"), encoding="utf-8-sig") as f:
        data_dir = json.load(f)["data_dir"]
    port = 2040
    settings_file = os.path.join(data_dir, "settings.json")
    if os.path.exists(settings_file):
        with open(settings_file, encoding="utf-8-sig") as f:
            port = int(json.load(f).get("port", port))
    return data_dir, port


class RegWebService(win32serviceutil.ServiceFramework):
    _svc_name_ = "RegWebRegistration"
    _svc_display_name_ = "Registration Web (التسجيل)"
    _svc_description_ = "registration_web (Django + waitress) on the LAN. Data: see service_config.json."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.process = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED, (self._svc_name_, ""))
        self.main()

    def main(self):
        data_dir, port = load_config()
        os.makedirs(os.path.join(data_dir, "logs"), exist_ok=True)
        log_file = open(os.path.join(data_dir, "logs", "service.log"), "a", encoding="utf-8", buffering=1)
        failed = False
        try:
            env = dict(os.environ, REGWEB_DATA_DIR=data_dir, DJANGO_SETTINGS_MODULE="regweb.settings")
            cmd = [VENV_PYTHON, "-m", "waitress", "--host=0.0.0.0", f"--port={port}",
                   "--threads=8", "regweb.wsgi:application"]
            log_file.write(f"\n===== service start: port {port}, data {data_dir} =====\n")
            self.process = subprocess.Popen(cmd, cwd=APP_DIR, env=env, stdout=log_file,
                                            stderr=subprocess.STDOUT,
                                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            while win32event.WaitForSingleObject(self.hWaitStop, 5000) != win32event.WAIT_OBJECT_0:
                if self.process.poll() is not None:
                    raise RuntimeError(f"waitress exited with code {self.process.returncode}")
        except Exception as exc:
            log_file.write(f"[service error] {exc}\n")
            servicemanager.LogErrorMsg(f"{self._svc_name_}: {exc}")
            failed = True
        finally:
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
            sys.exit(1)  # non-zero -> Windows recovery restarts it


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(RegWebService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(RegWebService)
