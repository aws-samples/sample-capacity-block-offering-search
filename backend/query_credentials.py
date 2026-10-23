"""Shared resolver for the EC2 Capacity Block query credential pool.

Single source of truth, resolved in priority order:
  1. SSM SecureString parameter named by QUERY_CREDENTIALS_PARAMETER
     (JSON array of {"access_key_id","secret_access_key"}) — recommended.
  2. EC2_QUERY_CREDENTIALS env var (same JSON array) — backward compatible.
  3. EC2_QUERY_ACCESS_KEY_ID / EC2_QUERY_SECRET_ACCESS_KEY env (single pair).
  4. [] — fall back to the Lambda execution role.

Credentials are never hardcoded and never logged; only the *count* is used for
auto-scaling the Step Functions concurrency.
"""
import os
import json
import logging

import boto3

logger = logging.getLogger()

_ssm = boto3.client('ssm')


def _parse_array(raw):
    pairs = []
    try:
        for c in json.loads(raw):
            ak = c.get('access_key_id')
            sk = c.get('secret_access_key')
            if ak and sk:
                pairs.append({'access_key_id': ak, 'secret_access_key': sk})
    except Exception as e:
        logger.warning(f"Failed to parse credential JSON: {str(e)}")
    return pairs


def _from_ssm():
    name = os.environ.get('QUERY_CREDENTIALS_PARAMETER')
    if not name:
        return []
    try:
        resp = _ssm.get_parameter(Name=name, WithDecryption=True)
        return _parse_array(resp['Parameter']['Value'])
    except _ssm.exceptions.ParameterNotFound:
        return []
    except Exception as e:
        logger.warning(f"Failed to read credentials from SSM '{name}': {str(e)}")
        return []


def _from_env_array():
    raw = os.environ.get('EC2_QUERY_CREDENTIALS')
    return _parse_array(raw) if raw else []


def load_credentials():
    """Return the resolved list of credential pairs ([] means use the role)."""
    creds = _from_ssm() or _from_env_array()
    if creds:
        return creds
    ak = os.environ.get('EC2_QUERY_ACCESS_KEY_ID')
    sk = os.environ.get('EC2_QUERY_SECRET_ACCESS_KEY')
    if ak and sk:
        return [{'access_key_id': ak, 'secret_access_key': sk}]
    return []


def count_accounts():
    """Number of usable credential pairs for concurrency sizing (minimum 1).

    1 means a single pair or the execution-role fallback.
    """
    return max(1, len(load_credentials()))
