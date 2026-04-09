import datetime
import base64
import json
import os
import traceback
from typing import Dict

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


def _normalize_domain(raw_domain: str) -> str:
    domain = raw_domain.strip()
    for prefix in ("https://", "http://"):
        if domain.startswith(prefix):
            domain = domain[len(prefix) :]
    return domain.split("/")[0]


def _optional_domain(raw_domain: str) -> str:
    if not raw_domain:
        return ""
    return _normalize_domain(raw_domain)


def _safe_int(raw_value: str, default_value: int) -> int:
    try:
        return max(1, int(raw_value))
    except (TypeError, ValueError):
        return default_value


def _is_truthy(value: str) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _load_private_key_from_file(private_key_file_path: str):
    if not private_key_file_path:
        raise ValueError("CF_PRIVATE_KEY_FILE_PATH is empty")

    with open(private_key_file_path, "r", encoding="utf-8") as key_file:
        key_text = key_file.read().strip()

    if not key_text:
        raise ValueError("Private key file is empty")

    try:
        parsed = json.loads(key_text)
        if isinstance(parsed, dict) and "private_key" in parsed:
            key_text = parsed["private_key"]
    except json.JSONDecodeError:
        pass

    if "\\n" in key_text:
        key_text = key_text.replace("\\n", "\n")

    return serialization.load_pem_private_key(key_text.encode("utf-8"), password=None)


def _cloudfront_safe_b64(raw: bytes) -> str:
    return (
        base64.b64encode(raw)
        .decode("utf-8")
        .replace("+", "-")
        .replace("=", "_")
        .replace("/", "~")
    )


def _build_cookie_values(resource_url: str, key_pair_id: str, private_key, expires_at):
    expires_epoch = int(expires_at.timestamp())
    canned_policy = {
        "Statement": [
            {
                "Resource": resource_url,
                "Condition": {"DateLessThan": {"AWS:EpochTime": expires_epoch}},
            }
        ]
    }
    policy_text = json.dumps(canned_policy, separators=(",", ":"))
    signature = private_key.sign(policy_text.encode("utf-8"), padding.PKCS1v15(), hashes.SHA1())

    return {
        "CloudFront-Expires": str(expires_epoch),
        "CloudFront-Signature": _cloudfront_safe_b64(signature),
        "CloudFront-Key-Pair-Id": key_pair_id,
    }


def _to_set_cookie_lines(cookie_values: Dict[str, str], cookie_domain: str, ttl_seconds: int):
    attrs = [
        "Path=/",
        "Secure",
        "HttpOnly",
        "SameSite=None",
        f"Max-Age={ttl_seconds}",
    ]
    if cookie_domain:
        attrs.insert(0, f"Domain={cookie_domain}")

    attr_text = "; ".join(attrs)
    return [f"{name}={value}; {attr_text}" for name, value in cookie_values.items()]


def handler(event, context):
    domain = _normalize_domain(os.environ["CF_DOMAIN"])
    key_pair_id = os.environ["CF_KEY_PAIR_ID"]
    private_key_file_path = os.environ["CF_PRIVATE_KEY_FILE_PATH"]
    debug_error_response = _is_truthy(os.environ.get("DEBUG_ERROR_RESPONSE", "true"))

    query = (event or {}).get("queryStringParameters") or {}
    resource_path = query.get("resource") or os.environ.get("DEFAULT_RESOURCE_PATH", "/*")
    if not resource_path.startswith("/"):
        resource_path = f"/{resource_path}"

    default_ttl = _safe_int(os.environ.get("DEFAULT_COOKIE_TTL_SECONDS", "300"), 300)
    ttl_seconds = _safe_int(query.get("expires_in"), default_ttl)
    cookie_domain = _optional_domain(query.get("cookie_domain") or os.environ.get("COOKIE_DOMAIN", ""))

    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=ttl_seconds)
    resource_url = f"https://{domain}{resource_path}"

    try:
        private_key = _load_private_key_from_file(private_key_file_path)
        cookie_values = _build_cookie_values(resource_url, key_pair_id, private_key, expires_at)
        set_cookie_lines = _to_set_cookie_lines(cookie_values, cookie_domain, ttl_seconds)

        return {
            "statusCode": 200,
            "headers": {
                "content-type": "application/json",
                "cache-control": "no-store",
            },
            "cookies": set_cookie_lines,
            "body": json.dumps(
                {
                    "message": "signed cookies generated",
                    "resource": resource_url,
                    "cookieDomain": cookie_domain or "(host-only)",
                    "expiresAt": expires_at.isoformat(),
                    "cookieNames": list(cookie_values.keys()),
                }
            ),
        }
    except Exception as err:  # noqa: BLE001
        response_body = {
            "message": "failed to generate signed cookies",
            "error": str(err),
        }

        if debug_error_response:
            response_body["debug"] = {
                "type": type(err).__name__,
                "traceback": traceback.format_exc(),
                "requestId": getattr(context, "aws_request_id", None),
                "request": {
                    "resource": resource_path,
                    "expiresIn": ttl_seconds,
                    "cookieDomain": cookie_domain,
                    "httpMethod": (event or {}).get("requestContext", {}).get("http", {}).get("method"),
                    "rawPath": (event or {}).get("rawPath"),
                },
                "config": {
                    "cfDomain": domain,
                    "cfKeyPairId": key_pair_id,
                    "privateKeyFilePath": private_key_file_path,
                },
            }

        return {
            "statusCode": 500,
            "headers": {
                "content-type": "application/json",
                "cache-control": "no-store",
            },
            "body": json.dumps(response_body),
        }
