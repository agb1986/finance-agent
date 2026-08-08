"""Generic HTTP client using requests.Session, shared across all skills."""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from common.logger import get_logger

USER_AGENT = "finance-agent/0.1 (+https://github.com/agb1986/finance-agent)"

# The pipeline runs unattended, so transient failures (CoinGecko 429s, feed
# hiccups, 5xx blips) must not fail a stage outright. Retry respects Retry-After.
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 1.0
RETRY_STATUSES = (429, 500, 502, 503, 504)


class HttpClient:
    """Thin wrapper around requests.Session with a fixed base URL and shared headers."""

    def __init__(
        self,
        base_url: str,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
        retries: int = DEFAULT_RETRIES,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        if headers:
            self.session.headers.update(headers)
        retry = Retry(
            total=retries,
            backoff_factor=DEFAULT_BACKOFF,
            status_forcelist=RETRY_STATUSES,
            allowed_methods=("GET", "POST"),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

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

    def post(self, path: str, json: dict | None = None) -> dict | list:
        """Perform a POST request with a JSON body and return the parsed JSON response.

        Raises:
            requests.HTTPError: If the server returns a 4xx or 5xx status code.
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        logger = get_logger()
        logger.debug(f"POST {url}")
        response = self.session.post(url, json=json, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
