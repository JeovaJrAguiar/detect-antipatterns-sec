from typing import Any, Dict

import requests

from observa.framework.base import Detector
from observa.security.rate_limit import enforce_remote_rate_limit
from observa.security.ssrf_guard import validate_remote_url


class RemoteDetector(Detector):
    def detect(self, data: Any) -> Dict:
        url = validate_remote_url(self.api_url)
        enforce_remote_rate_limit(url)
        session = requests.Session()
        session.max_redirects = 3
        response = session.post(url, json=data, timeout=10, allow_redirects=False)

        if response.is_redirect:
            raise ValueError("Remote detector requests must not redirect to another destination.")

        if response.status_code == 200:
            return response.json()

        raise ValueError(f"Remote detector request failed with status {response.status_code}: {response.text}")
