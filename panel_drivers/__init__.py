"""
Panel Drivers Package
=====================
Modular panel driver system for universal panel support.
"""

from .base import BasePanelDriver, PanelDriverRegistry
from .nine_router import NineRouterDriver
from .universal import UniversalPanelDriver

# Register all drivers
PanelDriverRegistry.register(NineRouterDriver)
PanelDriverRegistry.register(UniversalPanelDriver)


def get_driver(panel_url: str, page=None):
    """Auto-detect and return the appropriate panel driver."""
    driver_class = PanelDriverRegistry.detect_driver(page, panel_url)
    if driver_class is None:
        driver_class = UniversalPanelDriver
    
    return driver_class
