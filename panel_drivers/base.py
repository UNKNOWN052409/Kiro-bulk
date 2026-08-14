"""
Base Panel Driver Interface
===========================
All panel drivers must implement this interface.
Each driver handles: login, provider detection, account addition flow.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class BasePanelDriver(ABC):
    """Abstract base class for panel drivers."""
    
    name: str = "base"
    
    def __init__(self, panel_url: str, panel_password: str, **kwargs):
        self.panel_url = panel_url.rstrip('/')
        self.panel_password = panel_password
        self.extra = kwargs
    
    @abstractmethod
    def detect(self, page) -> bool:
        """Check if this driver matches the current panel URL/structure."""
        pass
    
    @abstractmethod
    def login(self, page) -> bool:
        """Login to the panel. Returns True on success."""
        pass
    
    @abstractmethod
    def add_account(self, page, kiro_email: str, password: str, 
                    mail_provider=None, **kwargs) -> bool:
        """Add a Kiro account to this panel. Returns True on success."""
        pass


class PanelDriverRegistry:
    """Registry of all available panel drivers."""
    
    _drivers = []
    
    @classmethod
    def register(cls, driver_class):
        cls._drivers.append(driver_class)
    
    @classmethod
    def detect_driver(cls, page, panel_url: str) -> Optional[BasePanelDriver]:
        """Auto-detect which driver to use based on URL and page structure."""
        for driver_class in cls._drivers:
            # Quick URL-based detection first
            if cls._url_match(panel_url, driver_class):
                return driver_class
            # Page-based detection
            try:
                if driver_class.detect(page):
                    return driver_class
            except Exception:
                pass
        # Fallback: try all drivers with URL patterns
        for driver_class in cls._drivers:
            if cls._url_match(panel_url, driver_class):
                return driver_class
        return None
    
    @classmethod
    def _url_match(cls, panel_url: str, driver_class) -> bool:
        """Check if the URL matches known patterns for this driver."""
        url_patterns = getattr(driver_class, 'url_patterns', [])
        for pattern in url_patterns:
            if pattern in panel_url:
                return True
        return False
    
    @classmethod
    def list_drivers(cls):
        return [d.name for d in cls._drivers]
