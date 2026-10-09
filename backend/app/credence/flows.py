"""Start / finish each Cloud SDK flow. Thin wrappers over the documented endpoints (architecture §5)."""
from app.credence.client import CredenceClient
from app.credence.parse import DigitalOutcome, parse_mdoc_result, parse_res_response

SUPPORTED_FLOWS = ("A", "B", "C")


def start(client: CredenceClient, flow: str) -> dict:
    """Begin a verification. Returns {session_id, browser: {...}} with only what the browser needs."""
    if flow == "A":  # Apple Wallet: DC API + ISO mdoc
        body = client.post("/v1/getDocRequest").json()
        return {"session_id": body["sessionId"],
                "browser": {"protocol": "org-iso-mdoc", "request": body["dcRequest"]}}
    if flow == "B":  # Google Wallet: DC API + OpenID4VP (unsigned request object)
        body = client.post("/dcapi/openid4vp/v1/initiate").json()
        return {"session_id": body["sessionId"], "browser": {"protocol": "openid4vp", "request": body["payload"]}}
    if flow == "C":  # Samsung Wallet and others: OpenID4VP Annex B via QR / deep link, then poll
        body = client.post("/openid4vp/v1/mdoc/initiate").json()
        return {"session_id": body["sessionId"],
                "browser": {"wallet_uri": body["walletUri"], "request_uri": body.get("requestUri")}}
    raise ValueError(f"Unsupported flow {flow}")


def complete(client: CredenceClient, flow: str, session_id: str, data: str) -> DigitalOutcome:
    """Flows A/B: send the wallet's encrypted response to Credence for validation."""
    path = "/v1/verifyDocRequest" if flow == "A" else "/dcapi/openid4vp/v1/validate"
    body = client.post(path, json={"sessionId": session_id, "data": data}).json()
    return parse_res_response(body)


def poll(client: CredenceClient, session_id: str) -> DigitalOutcome | None:
    """Flow C: None while the wallet hasn't answered yet (Credence returns 202)."""
    res = client.post("/openid4vp/v1/mdoc/result", json={"sessionId": session_id})
    if res.status_code == 202:
        return None
    return parse_mdoc_result(res.json())
