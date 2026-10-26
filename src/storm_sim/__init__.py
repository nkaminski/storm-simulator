"""storm_sim - Physics-accurate E1.31 lighting and spatial audio thunderstorm simulator."""

__version__ = "0.1.0"

from .audio import AudioEngine
from .engine import StormCoordinator
from .lighting import E131LightingEngine
from .models import StormState, StrikeEvent, StrokePulse
from .osc_control import OSCController
from .physics import PhysicsEngine
from .synthesis import ThunderSynthesizer

__all__ = [
    "__version__",
    "AudioEngine",
    "E131LightingEngine",
    "OSCController",
    "PhysicsEngine",
    "StormCoordinator",
    "StormState",
    "StrikeEvent",
    "StrokePulse",
    "ThunderSynthesizer",
]
