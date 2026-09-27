"""Handler'lar routerlari."""
from .start import router as start_router
from .schools import router as schools_router
from .admin import router as admin_router

__all__ = ["start_router", "schools_router", "admin_router"]