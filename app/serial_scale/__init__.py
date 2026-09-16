"""
Serial Scale Module for Universal Hardware Bridge
Supports Mettler Toledo (MT-SICS), Shinko/ViBRA, A&D, Generic Continuous, and Simulator
"""

from .protocols import PROTOCOLS, parse_scale_line
from .scale_manager import scale_manager, ScaleInstance

__all__ = ["PROTOCOLS", "parse_scale_line", "scale_manager", "ScaleInstance"]
