import traceback
import sys

try:
    from main import CertificateManagerApp
    app = CertificateManagerApp()
    print("SUCCESS")
    # app.destroy()
except Exception as e:
    print("ERROR:")
    traceback.print_exc()
