#!/usr/bin/env python3
"""
Mint an M2M JWT for AgentCore Gateway (Cognito client_credentials).

Reads gateway-credentials.json by default (created by create_mcp_gateway.py).
Falls back to CLI flags / env vars for an already-created Cognito pool.

Usage:
  .venv/bin/python scripts/get_gateway_token.py
  .venv/bin/python scripts/get_gateway_token.py --credentials gateway-credentials.json
  export GATEWAY_TOKEN="$(.venv/bin/python scripts/get_gateway_token.py)"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CREDS = ROOT / "gateway-credentials.json"


def load_bundle(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing {path}\n"
            "Create a gateway first:\n"
            "  .venv/bin/python scripts/create_mcp_gateway.py --name lauki-demo-gateway --with-lambda-target\n"
            "Or pass --user-pool-id / --client-id / --client-secret / --domain / --scope manually."
        )
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials", default=str(DEFAULT_CREDS))
    parser.add_argument("--region", default=None)
    parser.add_argument("--user-pool-id", default=None)
    parser.add_argument("--client-id", default=None)
    parser.add_argument("--client-secret", default=None)
    parser.add_argument("--domain", default=None)
    parser.add_argument("--scope", default=None)
    parser.add_argument("--token-endpoint", default=None)
    args = parser.parse_args()

    creds_path = Path(args.credentials)
    cognito: dict = {}
    region = args.region or os.getenv("AWS_REGION", "us-west-2")

    if creds_path.is_file():
        bundle = load_bundle(creds_path)
        cognito = bundle.get("cognito") or {}
        region = args.region or bundle.get("region") or region

    user_pool_id = args.user_pool_id or cognito.get("user_pool_id")
    client_id = args.client_id or cognito.get("client_id") or os.getenv("COGNITO_CLIENT_ID")
    client_secret = (
        args.client_secret
        or cognito.get("client_secret")
        or os.getenv("COGNITO_CLIENT_SECRET")
    )
    domain = args.domain or cognito.get("domain_prefix")
    scope = args.scope or cognito.get("scope") or os.getenv("COGNITO_SCOPE")
    token_endpoint = args.token_endpoint or cognito.get("token_endpoint")

    # If secret missing but we have pool+client, try describe (works for confidential clients)
    if client_id and user_pool_id and not client_secret:
        import boto3

        client_secret = (
            boto3.client("cognito-idp", region_name=region)
            .describe_user_pool_client(UserPoolId=user_pool_id, ClientId=client_id)[
                "UserPoolClient"
            ]
            .get("ClientSecret")
        )

    if not token_endpoint:
        if not domain:
            print("Need --domain or cognito.domain_prefix in credentials file", file=sys.stderr)
            raise SystemExit(1)
        token_endpoint = f"https://{domain}.auth.{region}.amazoncognito.com/oauth2/token"

    if not all([client_id, client_secret, scope]):
        print(
            "Missing client_id / client_secret / scope.\n"
            f"Expected file: {creds_path}\n"
            "Or pass flags / COGNITO_* env vars.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    resp = httpx.post(
        token_endpoint,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30.0,
    )
    if resp.status_code >= 400:
        print(f"Token request failed ({resp.status_code}): {resp.text}", file=sys.stderr)
        raise SystemExit(1)

    print(resp.json()["access_token"])


if __name__ == "__main__":
    main()
