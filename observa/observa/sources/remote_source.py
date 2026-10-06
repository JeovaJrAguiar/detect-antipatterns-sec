from typing import Any

import requests

from observa.framework.base import Source
from observa.security.rate_limit import enforce_remote_rate_limit
from observa.security.ssrf_guard import validate_remote_url


class RemoteSource(Source):
    def load(self) -> Any:
        url = validate_remote_url(self.api_url)
        enforce_remote_rate_limit(url)
        session = requests.Session()
        session.max_redirects = 3
        response = session.get(url, timeout=10, allow_redirects=False)

        if response.is_redirect:
            raise ValueError("Remote source requests must not redirect to another destination.")

        if response.status_code == 200:
            return response.json()

        raise ValueError(f"Remote source request failed with status {response.status_code}: {response.text}")