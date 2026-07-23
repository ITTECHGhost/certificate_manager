# =============================================================================
# api_config.py — Connection configuration for the FastAPI server
# 
# Defines the core API endpoints and networking parameters used to 
# communicate between the frontend client and backend FastAPI service.
# =============================================================================
API_HOST = "127.0.0.1"  # Change this to your server's IP address (e.g. "172.50.0.50")
API_PORT = 2030
API_URL = f"http://{API_HOST}:{API_PORT}"
