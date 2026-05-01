"""SDeck — GitOps Stream Deck provisioner for Home Assistant."""

from sdeck.main import main
from sdeck.profile import DeviceProfile, TemplateSlot

__all__ = ["DeviceProfile", "TemplateSlot", "main"]
