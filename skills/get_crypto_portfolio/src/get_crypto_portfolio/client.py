"""Crypto.com Exchange API client."""

import hashlib
import hmac
import time

from common.http_client import HttpClient
from common.logger import get_logger

CRYPTO_BASE_URL = "https://api.crypto.com/exchange/v1"


def make_client() -> HttpClient:
    """Create an HttpClient pre-configured for the Crypto.com Exchange API."""
    return HttpClient(base_url=CRYPTO_BASE_URL)


def _sign_request(method: str, params: dict, api_key: str, api_secret: str) -> dict:
    """Build and sign a private API request body using HMAC-SHA256.

    Args:
        method:     API method name, e.g. "private/user-balance".
        params:     Request parameters dict (may be empty).
        api_key:    Crypto.com API key.
        api_secret: Crypto.com API secret.

    Returns:
        A fully signed request body dict ready to POST as JSON.
    """
    request_id = int(time.time() * 1000)
    nonce = request_id

    # Params string: keys sorted alphabetically, key+value concatenated
    params_str = "".join(f"{k}{v}" for k, v in sorted(params.items()))

    sig_payload = method + str(request_id) + api_key + params_str + str(nonce)
    sig = hmac.new(
        bytes(api_secret, "utf-8"),
        msg=bytes(sig_payload, "utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    return {
        "id": request_id,
        "method": method,
        "api_key": api_key,
        "params": params,
        "nonce": nonce,
        "sig": sig,
    }


def _extract_result(response: dict, method: str) -> dict | list:
    """Check for API errors and extract the result payload.

    Args:
        response: Raw JSON response from the Crypto.com API.
        method:   The method name (used in error messages).

    Returns:
        The value of response["result"]["data"].

    Raises:
        RuntimeError: If the API returned a non-zero error code.
    """
    logger = get_logger()
    code = response.get("code", -1)
    if code != 0:
        msg = response.get("message", "unknown error")
        detail = response.get("detail", "")
        raise RuntimeError(f"Crypto.com API error for {method}: code={code} {msg} {detail}".strip())

    result = response.get("result", {})
    data = result.get("data", result)
    logger.debug(
        f"_extract_result: {method} returned {len(data) if isinstance(data, list) else 1} item(s)"
    )
    return data


def fetch_user_balance(client: HttpClient, api_key: str, api_secret: str) -> list[dict]:
    """Fetch the user's account balance.

    Returns:
        The ``data`` list from the ``private/user-balance`` response.
    """
    method = "private/user-balance"
    body = _sign_request(method, {}, api_key, api_secret)
    response = client.post(method, json=body)
    return _extract_result(response, method)


def fetch_positions(client: HttpClient, api_key: str, api_secret: str) -> list[dict]:
    """Fetch all open positions.

    Returns:
        The ``data`` list from the ``private/get-positions`` response.
    """
    method = "private/get-positions"
    body = _sign_request(method, {}, api_key, api_secret)
    response = client.post(method, json=body)
    return _extract_result(response, method)
