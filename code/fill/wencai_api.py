import json
import os
import secrets
import urllib.request
import urllib.error
from typing import Optional, Dict, List, Any

class WencaiAPI:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("IWENCAI_API_KEY", "")
        self.base_url = "https://openapi.iwencai.com/v1/query2data"

    def _generate_trace_id(self) -> str:
        return secrets.token_hex(32)

    def query(self, query_str: str, page: int = 1, limit: int = 10) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("IWENCAI_API_KEY is not set.")

        trace_id = self._generate_trace_id()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Claw-Call-Type": "normal",
            "X-Claw-Skill-Id": "hithink-market-query",
            "X-Claw-Skill-Version": "1.0.0",
            "X-Claw-Plugin-Id": "none",
            "X-Claw-Plugin-Version": "none",
            "X-Claw-Trace-Id": trace_id,
        }

        data = {
            "query": query_str,
            "page": str(page),
            "limit": str(limit),
            "is_cache": "1",
            "expand_index": "true",
            "log_id": trace_id
        }

        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                resp_data = response.read().decode("utf-8")
                return json.loads(resp_data)
        except urllib.error.HTTPError as e:
            resp_body = e.read().decode("utf-8")
            try:
                error_detail = json.loads(resp_body)
            except json.JSONDecodeError:
                error_detail = resp_body
            raise Exception(f"API Error {e.code}: {error_detail}")
        except Exception as e:
            raise Exception(f"Query failed: {str(e)}")

def parse_num(val) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).replace('%', '').replace(',', '').strip()
    try:
        return float(val_str)
    except:
        return 0.0
