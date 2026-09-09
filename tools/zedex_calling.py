import requests

from models import CreateUpdateBill, ProductQuery

_JSON_HEADERS = {"accept": "application/json",
                 "Content-Type": "application/json"}

zedex_api_base_url: str = "http://localhost:61815/api/tools"
CUSTOMERS_URL = f"{zedex_api_base_url}/customers"
LOOKUPS_URL = f"{zedex_api_base_url}/lookups"
SEARCH_URL = f"{zedex_api_base_url}/products/search"
BILLS_URL = f"{zedex_api_base_url}/bills"


def _request_json(method, url, **kwargs):
    """Call the Zedex tools API and always return JSON the LLM can read.

    HTTP 4xx/5xx responses are NOT raised — the Zedex tools endpoints return a
    JSON body describing what went wrong (e.g. "Bill not found.", validation
    errors), and the model should see that and react instead of the whole
    chat request failing with a 500. Only connection-level failures (server
    down, DNS, timeout) still raise.
    """
    response = requests.request(
        method, url, headers=_JSON_HEADERS, timeout=30, **kwargs)
    try:
        body = response.json() if response.text.strip() else None
    except ValueError:
        body = response.text

    if response.status_code >= 400:
        return {"error": True, "status": response.status_code, "detail": body}
    return body


def find_customer(search=None):
    params = {"search": search} if search else None
    return _request_json("GET", CUSTOMERS_URL, params=params)


def get_lookups():
    return _request_json("GET", LOOKUPS_URL)


def search_product(products):

    return _request_json("POST", SEARCH_URL, json=products)


def get_bill(id_or_invoice_number):
    return _request_json("GET", f"{BILLS_URL}/{id_or_invoice_number}")


def create_or_update_bill(bill_data):
    return _request_json("POST", BILLS_URL, json=bill_data)
