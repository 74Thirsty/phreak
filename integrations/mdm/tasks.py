import time
from .server import MDMService
from .utils import timestamp

def sync_devices(interval: int = 300):
    service = MDMService()
    while True:
        devices = service.list_devices()
        print(f"[{timestamp()}] Synced {len(devices)} devices.")
        time.sleep(interval)
