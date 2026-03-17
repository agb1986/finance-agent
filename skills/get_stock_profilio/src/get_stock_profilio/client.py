"""Trading212 API client."""

import base64

from common.http_client import HttpClient

TRADING212_BASE_URL = "https://live.trading212.com"


def make_client(api_key: str, api_secret: str) -> HttpClient:
    """Create an HttpClient pre-configured for the Trading212 API."""
    encoded = base64.b64encode(f"{api_key}:{api_secret}".encode()).decode()
    return HttpClient(
        base_url=TRADING212_BASE_URL,
        headers={"Authorization": f"Basic {encoded}"},
    )


def fetch_account_summary(client: HttpClient) -> dict:
    """Fetch the equity account summary.

    Returns the raw JSON from GET /api/v0/equity/account/summary.
    """
    return client.get("/api/v0/equity/account/summary")


def fetch_positions(client: HttpClient) -> list[dict]:
    """Fetch all open equity positions.

    Returns the raw JSON list from GET /api/v0/equity/positions.
    """
    return client.get("/api/v0/equity/positions")
