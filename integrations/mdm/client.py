import requests
from . import config

class MDMClient:
    """Lightweight REST client for hmdm-server endpoints."""

    def __init__(self):
        self.base_url = config.MDM_BASE_URL.rstrip("/")
        self.headers = {"Authorization": f"Bearer {config.MDM_API_KEY}"}

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def get_devices(self):
        r = requests.get(self._url("api/devices"), headers=self.headers, timeout=config.MDM_TIMEOUT)
        r.raise_for_status()
        return r.json()

    def get_policies(self):
        r = requests.get(self._url("api/policies"), headers=self.headers, timeout=config.MDM_TIMEOUT)
        r.raise_for_status()
        return r.json()

    def push_policy(self, device_id: int, policy_id: int):
        r = requests.post(
            self._url(f"api/devices/{device_id}/applyPolicy"),
            headers=self.headers,
            json={"policyId": policy_id},
            timeout=config.MDM_TIMEOUT
        )
        r.raise_for_status()
        return r.json()
