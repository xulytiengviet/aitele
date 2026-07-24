"""Shared transport: auth header, httpx call, error mapping, retries.

Retries cover network failures and 429/5xx only (with backoff). Logic errors
(401/403/404/422) are never retried — repeating them cannot help.
"""
from __future__ import annotations

import time
from typing import Any, Optional

import httpx

from ._version import API_VERSION, __version__
from .errors import APIConnectionError, error_from_response

DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 2


class Transport:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required (e.g. 'sk_live_...').")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self._external_client = http_client is not None
        self._client = http_client or httpx.Client(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": f"ai-telecom-python/{__version__}",
                "Accept": "application/json",
            },
        )
        # A caller-supplied client still needs the auth header set.
        if self._external_client:
            self._client.headers.setdefault("Authorization", f"Bearer {api_key}")

    def _url(self, path: str) -> str:
        # "/calls" → "{base}/api/v1/calls"
        return f"{self.base_url}/api/{API_VERSION}{path}"

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json: Any = None,
        files: Optional[dict] = None,
        data: Optional[dict] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """``files``/``data`` send multipart (file upload); ``json`` sends JSON.

        ``timeout`` overrides the client default for this one request — uploads
        of a 50MB document need far longer than a normal API call.
        """
        url = self._url(path)
        last_exc: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                resp = self._client.request(
                    method, url, params=params, json=json, files=files, data=data,
                    **({'timeout': timeout} if timeout is not None else {}),
                )
            except httpx.HTTPError as exc:
                last_exc = APIConnectionError(f"Could not reach {url}: {exc}")
                if attempt < self.max_retries:
                    time.sleep(_backoff(attempt))
                    continue
                raise last_exc from exc

            if resp.status_code < 400:
                if resp.status_code == 204 or not resp.content:
                    return None
                return resp.json()

            # Error status — decide whether it is worth retrying
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < self.max_retries:
                    retry_after = _parse_retry_after(resp)
                    time.sleep(retry_after if retry_after is not None else _backoff(attempt))
                    continue
            raise _raise_status(resp)

        # unreachable in practice
        raise last_exc or APIConnectionError("Request failed for an unknown reason.")

    def close(self) -> None:
        if not self._external_client:
            self._client.close()

    def __enter__(self) -> "Transport":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def _backoff(attempt: int) -> float:
    return min(0.5 * (2 ** attempt), 8.0)


def _parse_retry_after(resp: httpx.Response) -> Optional[float]:
    val = resp.headers.get("Retry-After")
    if not val:
        return None
    try:
        return float(val)
    except ValueError:
        return None


def _raise_status(resp: httpx.Response):
    code = None
    message = resp.text
    body: Any = None
    try:
        body = resp.json()
        if isinstance(body, dict):
            err = body.get("error")
            if isinstance(err, dict):
                code = err.get("code")
                message = err.get("message", message)
            elif isinstance(err, str):
                message = err
    except Exception:
        pass

    exc = error_from_response(resp.status_code, code, message or "Unknown error", body)
    if resp.status_code == 429:
        exc.retry_after = _parse_retry_after(resp)  # type: ignore[attr-defined]
    return exc
