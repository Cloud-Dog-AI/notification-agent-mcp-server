#!/usr/bin/env python3
# Copyright 2026 Cloud-Dog, Viewdeck Engineering Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""SSL contexts for explicitly configured private certificate authorities."""

import ssl


def private_ca_context(cafile: str) -> ssl.SSLContext:
    """Build a verified context compatible with the deployed private CA.

    Python 3.13 enables OpenSSL strict X.509 checking in its default client
    context.  The deployed Cloud-Dog root predates the requirement that a CA's
    basic-constraints extension be marked critical.  Clearing only the strict
    flag preserves certificate-chain and hostname verification while allowing
    that explicitly configured legacy root.
    """
    context = ssl.create_default_context(cafile=cafile)
    strict_flag = getattr(ssl, "VERIFY_X509_STRICT", 0)
    if strict_flag:
        context.verify_flags &= ~strict_flag
    return context
