# services/http_client.py
import certifi
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def build_session() -> requests.Session:
    s = requests.Session()
    s.verify = certifi.where()

    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST", "PUT", "DELETE", "PATCH"),
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)

    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

session = build_session()