"""Generic HTTP client using requests.Session, shared across all skills."""

import requests

from common.logger import get_logger


class HttpClient:
    """Thin wrapper around requests.Session with a fixed base URL and shared headers."""

    def __init__(
        self,
        base_url: str,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        if headers:
            self.session.headers.update(headers)

    def get(self, path: str, params: dict | None = None) -> dict | list:
        """Perform a GET request and return the parsed JSON response.

        Raises:
            requests.HTTPError: If the server returns a 4xx or 5xx status code.
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        logger = get_logger()
        logger.debug(f"GET {url} params={params!r}")
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
