"""Execution backend implementations."""

from .in_process import execute_one_in_process, execute_ready_wave

__all__ = ["execute_one_in_process", "execute_ready_wave"]
