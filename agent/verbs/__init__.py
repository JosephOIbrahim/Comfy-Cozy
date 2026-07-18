"""Verb engines for the artist-facing CLI surface (``cozy <verb> <object>``).

Each module holds the logic for one verb — FIND (models/nodes discovery),
SEE (execution feedback rendering), OPEN (browser canvas round-trip) — kept
separate from ``agent/cli.py`` so the Typer layer stays thin wiring. Engines
never open non-loopback sockets: local-first is the contract, not a feature.
"""
