"""HTTP client helpers that keep backend traffic independent of shell proxies."""

import os
from typing import Any

import httpx


def configure_proxy_bypass() -> None:
    """Disable environment proxy discovery for this project's HTTP clients."""
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"


def create_direct_httpx_client(**kwargs: Any) -> httpx.Client:
    """Create an HTTPX client that never reads HTTP_PROXY or HTTPS_PROXY."""
    return httpx.Client(trust_env=False, **kwargs)
