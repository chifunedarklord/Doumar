"""
TaskFlow - Database Layer (Legacy Facade)
This module acts as a facade, forwarding calls to the new Repositories layer
to maintain backward compatibility with existing services and UI screens.
"""
from core.repositories import Storage

# Cung cấp Storage cho các module cũ
__all__ = ["Storage"]
