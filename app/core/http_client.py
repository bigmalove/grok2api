"""
HTTP client compatibility layer.

This module prefers ``curl_cffi`` for browser impersonation. When unavailable
(common on Android Termux), it transparently falls back to ``aiohttp``.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional
from urllib.parse import urlparse

try:
    from curl_cffi.requests import AsyncSession as _CurlAsyncSession
    from curl_cffi.requests.errors import RequestsError

    _HAS_CURL_CFFI = True
except Exception:  # pragma: no cover - fallback path
    _CurlAsyncSession = None
    _HAS_CURL_CFFI = False

    class RequestsError(Exception):
        """Fallback request error type (curl_cffi unavailable)."""

        pass


def _to_timeout(value: Any):
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _normalize_proxies(value: Any) -> Optional[dict[str, str]]:
    if not value:
        return None
    if isinstance(value, dict):
        out: dict[str, str] = {}
        for key, proxy in value.items():
            if not proxy:
                continue
            k = str(key).lower()
            if k in ("http", "https"):
                out[k] = str(proxy)
        return out or None
    if isinstance(value, str):
        return {"http": value, "https": value}
    return None


def _pick_proxy(url: str, proxies: Optional[dict[str, str]]) -> Optional[str]:
    if not proxies:
        return None
    scheme = (urlparse(url).scheme or "https").lower()
    return proxies.get(scheme) or proxies.get("https") or proxies.get("http")


if not _HAS_CURL_CFFI:  # pragma: no cover - requires curl_cffi absence
    import aiohttp
    import certifi
    import ssl
    try:
        from aiohttp_socks import ProxyConnector
    except Exception:  # pragma: no cover - optional dependency
        ProxyConnector = None

    def _ssl_for_verify(verify: Any):
        if verify in (False, 0, "0", "false", "False", "no", "off"):
            return False
        ctx = ssl.create_default_context()
        ctx.load_verify_locations(certifi.where())
        return ctx

    class _AiohttpResponse:
        def __init__(
            self,
            response: aiohttp.ClientResponse,
            *,
            body: Optional[bytes] = None,
            owned_session: Optional[aiohttp.ClientSession] = None,
        ):
            self._response = response
            self._body = body
            self._closed = False
            self._owned_session = owned_session
            self.status_code = response.status
            self.headers = response.headers

        async def _read_body(self) -> bytes:
            if self._body is None:
                self._body = await self._response.read()
                await self.close()
            return self._body

        @property
        def content(self) -> bytes:
            return self._body or b""

        async def text(self) -> str:
            body = await self._read_body()
            return body.decode("utf-8", errors="replace")

        def json(self) -> Any:
            if self._body is None:
                raise RuntimeError(
                    "JSON body not available yet. Read stream content first."
                )
            if not self._body:
                return {}
            return json.loads(self._body.decode("utf-8", errors="replace"))

        async def aiter_content(self, chunk_size: int = 64 * 1024):
            if self._body is not None:
                if self._body:
                    yield self._body
                return

            try:
                async for chunk in self._response.content.iter_chunked(chunk_size):
                    if chunk:
                        yield chunk
            finally:
                await self.close()

        async def aiter_lines(self):
            if self._body is not None:
                text = self._body.decode("utf-8", errors="replace")
                for line in text.splitlines():
                    yield line
                return

            buf = b""
            try:
                async for chunk in self._response.content.iter_chunked(8192):
                    if not chunk:
                        continue
                    buf += chunk
                    while b"\n" in buf:
                        raw, buf = buf.split(b"\n", 1)
                        yield raw.decode("utf-8", errors="replace").rstrip("\r")
                if buf:
                    yield buf.decode("utf-8", errors="replace").rstrip("\r")
            finally:
                await self.close()

        async def close(self):
            if self._closed:
                return
            self._closed = True
            try:
                self._response.release()
            except Exception:
                pass
            if self._owned_session and not self._owned_session.closed:
                try:
                    await self._owned_session.close()
                except Exception:
                    pass
            await asyncio.sleep(0)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            await self.close()

    class _AiohttpAsyncSession:
        def __init__(self, **kwargs: Any):
            headers = kwargs.pop("headers", None)
            cookies = kwargs.pop("cookies", None)
            timeout = _to_timeout(kwargs.pop("timeout", None))
            verify = kwargs.pop("verify", True)
            proxy = kwargs.pop("proxy", None)
            proxies = kwargs.pop("proxies", None)

            # Unsupported by aiohttp; accepted for compatibility.
            kwargs.pop("impersonate", None)
            kwargs.pop("http_version", None)

            proxy_map = _normalize_proxies(proxies)
            if proxy:
                proxy_map = proxy_map or {}
                proxy_map["http"] = str(proxy)
                proxy_map["https"] = str(proxy)
            self._default_proxies = proxy_map

            client_timeout = (
                aiohttp.ClientTimeout(total=timeout) if timeout is not None else None
            )
            self._session = aiohttp.ClientSession(
                headers=headers,
                cookies=cookies,
                timeout=client_timeout,
                connector=aiohttp.TCPConnector(ssl=_ssl_for_verify(verify)),
                trust_env=True,
            )

        async def request(self, method: str, url: str, **kwargs: Any):
            stream = bool(kwargs.pop("stream", False))
            allow_redirects = kwargs.pop("allow_redirects", True)
            timeout = _to_timeout(kwargs.pop("timeout", None))
            verify = kwargs.pop("verify", None)

            proxy = kwargs.pop("proxy", None)
            proxies = kwargs.pop("proxies", None)
            kwargs.pop("impersonate", None)
            kwargs.pop("http_version", None)

            proxy_map = dict(self._default_proxies or {})
            extra = _normalize_proxies(proxies)
            if extra:
                proxy_map.update(extra)
            if proxy:
                proxy_map["http"] = str(proxy)
                proxy_map["https"] = str(proxy)
            proxy_url = _pick_proxy(url, proxy_map)

            if timeout is not None:
                kwargs["timeout"] = aiohttp.ClientTimeout(total=timeout)
            if verify is not None:
                kwargs["ssl"] = _ssl_for_verify(verify)

            use_socks_proxy = bool(proxy_url) and proxy_url.lower().startswith("socks")
            if use_socks_proxy and ProxyConnector is None:
                raise RequestsError(
                    "SOCKS proxy requested but aiohttp-socks is not installed"
                )

            try:
                if use_socks_proxy:
                    temp_timeout = kwargs.get("timeout")
                    if not isinstance(temp_timeout, aiohttp.ClientTimeout):
                        temp_timeout = None
                    temp_session = aiohttp.ClientSession(
                        timeout=temp_timeout,
                        connector=ProxyConnector.from_url(proxy_url),
                        trust_env=True,
                    )
                    try:
                        resp = await temp_session.request(
                            method.upper(),
                            url,
                            allow_redirects=allow_redirects,
                            **kwargs,
                        )
                    except Exception:
                        await temp_session.close()
                        raise
                    owner = temp_session
                else:
                    resp = await self._session.request(
                        method.upper(),
                        url,
                        allow_redirects=allow_redirects,
                        proxy=proxy_url,
                        **kwargs,
                    )
                    owner = None
                if stream:
                    return _AiohttpResponse(resp, owned_session=owner)

                body = await resp.read()
                wrapped = _AiohttpResponse(resp, body=body, owned_session=owner)
                await wrapped.close()
                return wrapped
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                raise RequestsError(str(e)) from e

        async def get(self, url: str, **kwargs: Any):
            return await self.request("GET", url, **kwargs)

        async def post(self, url: str, **kwargs: Any):
            return await self.request("POST", url, **kwargs)

        async def delete(self, url: str, **kwargs: Any):
            return await self.request("DELETE", url, **kwargs)

        async def close(self):
            await self._session.close()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            await self.close()


class AsyncSession:
    """Compatibility AsyncSession used across reverse services."""

    def __init__(self, **kwargs: Any):
        if _HAS_CURL_CFFI:
            self._impl = _CurlAsyncSession(**kwargs)  # type: ignore[misc]
        else:
            self._impl = _AiohttpAsyncSession(**kwargs)  # type: ignore[name-defined]

    async def request(self, method: str, url: str, **kwargs: Any):
        return await self._impl.request(method, url, **kwargs)

    async def get(self, url: str, **kwargs: Any):
        return await self._impl.get(url, **kwargs)

    async def post(self, url: str, **kwargs: Any):
        return await self._impl.post(url, **kwargs)

    async def delete(self, url: str, **kwargs: Any):
        return await self._impl.delete(url, **kwargs)

    async def close(self):
        return await self._impl.close()

    async def __aenter__(self):
        return await self._impl.__aenter__()

    async def __aexit__(self, exc_type, exc, tb):
        return await self._impl.__aexit__(exc_type, exc, tb)

    def __getattr__(self, name: str):
        return getattr(self._impl, name)


__all__ = ["AsyncSession", "RequestsError"]

