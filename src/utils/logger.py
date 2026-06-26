#!/usr/bin/env python3
# Copyright 2026 Cloud-Dog, Viewdeck Engineering Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""Platform logging compatibility exports.

This module stays intentionally small for W28A-93b-R1. The implementation
resides in ``platform_logging_core`` and is backed by ``cloud_dog_logging``.
"""

from __future__ import annotations

from src.utils.platform_logging_core import (
    ContextLogger,
    PlatformContextMiddleware,
    PlatformJSONFormatter,
    apply_platform_context,
    get_context_logger,
    get_logger,
    setup_logger,
    setup_sidecar_logger,
)

__all__ = [
    "ContextLogger",
    "PlatformContextMiddleware",
    "PlatformJSONFormatter",
    "apply_platform_context",
    "get_context_logger",
    "get_logger",
    "setup_logger",
    "setup_sidecar_logger",
]
