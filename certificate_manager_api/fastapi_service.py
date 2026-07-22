# =============================================================================
# fastapi_service.py — Windows Service wrapper for FastAPI
# =============================================================================
#
# HOW TO USE (Run Command Prompt as Administrator):
#   Install service:
#       C:\Users\IT_TECK\AppData\Local\Python\pythoncore-3.14-64\python.exe fastapi_service.py install
#   Start service:
#       C:\Users\IT_TECK\AppData\Local\Python\pythoncore-3.14-64\python.exe fastapi_service.py start
#   Stop service:
#       C:\Users\IT_TECK\AppData\Local\Python\pythoncore-3.14-64\python.exe fastapi_service.py stop
#   Uninstall service:
#       C:\Users\IT_TECK\AppData\Local\Python\pythoncore-3.14-64\python.exe fastapi_service.py remove
#
# =============================================================================

import sys
import os
import win32serviceutil
import win32service
import win32event
import servicemanager
import subprocess

class FastAPIWindowsService(win32serviceutil.ServiceFramework):
    _svc_name_ = "FastAPICertificateManager"
    _svc_display_name_ = "FastAPI Certificate Manager Service"
    _svc_description_ = "Background FastAPI Uvicorn service for the Certificate Manager application."
    
    # Establish a dependency on the apache24 service
    _svc_deps_ = ["apache24"]

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.is_running = True

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.is_running = False
        
        # Safe termination of the uvicorn sub-process
        try:
            subprocess.run([
                "powershell", 
                "-Command", 
                "Get-CimInstance Win32_Process -Filter \"Name = 'python.exe' AND CommandLine LIKE '%uvicorn%'\" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
            ], capture_output=True)
        except Exception:
            pass

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.main()

    def main(self):
        python_exe = r"C:\Users\IT_TECK\AppData\Local\Python\pythoncore-3.14-64\python.exe"
        server_dir = r"C:\AppServ\www\certificate_manager_api"
        
        # Start the FastAPI server using Uvicorn
        process = subprocess.Popen(
            [python_exe, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "2030"],
            cwd=server_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Block until the service stop signal is received
        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
        
        # Terminate process when service stops
        try:
            process.terminate()
            process.wait(timeout=3)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(FastAPIWindowsService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(FastAPIWindowsService)
