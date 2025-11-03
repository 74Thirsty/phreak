import os

MDM_BASE_URL = os.getenv("MDM_BASE_URL", "http://localhost:8080/hmdm")
MDM_API_KEY = os.getenv("MDM_API_KEY", "")
MDM_TIMEOUT = int(os.getenv("MDM_TIMEOUT", "10"))
