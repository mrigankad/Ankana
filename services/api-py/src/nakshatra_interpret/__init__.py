"""Deterministic interpretation engine: turns a VedicChartArtifact into a
sectioned, evidence-cited reading."""

from .reading import build_reading

__all__ = ["build_reading"]
