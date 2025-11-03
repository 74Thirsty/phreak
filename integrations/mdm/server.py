from .client import MDMClient
from .models import Device, Policy

class MDMService:
    """Server-side integration wrapper for internal modules."""

    def __init__(self):
        self.client = MDMClient()

    def list_devices(self):
        data = self.client.get_devices()
        return [Device(**d) for d in data]

    def list_policies(self):
        data = self.client.get_policies()
        return [Policy(**p) for p in data]

    def apply_policy(self, device_id: int, policy_id: int):
        return self.client.push_policy(device_id, policy_id)
