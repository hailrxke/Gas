"""Download the official NEIS school directory. No API keys are stored in output."""

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ENDPOINT = "https://open.neis.go.kr/hub/schoolInfo"


def convert(row):
    return dict(
        id="neis:" + row["ATPT_OFCDC_SC_CODE"] + ":" + row["SD_SCHUL_CODE"],
        name=row["SCHUL_NM"],
        englishName=(row.get("ENG_SCHUL_NM") or ""),
        region=row.get("LCTN_SC_NM") or row["ATPT_OFCDC_SC_NM"],
        address=(row.get("ORG_RDNMA") or ""),
        kind=row.get("SCHUL_KND_SC_NM", ""),
    )


def fetch(key, region=None):
    rows = []
    page = 1
    while True:
        query = dict(KEY=key, Type="json", pIndex=page, pSize=1000)
        if region:
            query["ATPT_OFCDC_SC_CODE"] = region
        # Never log the request URL: it contains the API key.
        with urlopen(ENDPOINT + "?" + urlencode(query), timeout=30) as response:
            data = json.load(response)
        if "schoolInfo" not in data:
            code = data.get("RESULT", {}).get("CODE", "unknown")
            if code == "INFO-200" and rows:
                break
            raise RuntimeError("NEIS request failed: " + code)
        parts = data["schoolInfo"]
        records = next((part["row"] for part in parts if "row" in part), [])
        if not records:
            break
        rows.extend(records)
        heads = next((part["head"] for part in parts if "head" in part), [])
        total = next(
            (h["list_total_count"] for h in heads if "list_total_count" in h), None
        )
        if total is not None and page * 1000 >= int(total):
            break
        page += 1
        if page > 100:
            raise RuntimeError("Unexpected pagination; import aborted")
    # The pilot targets secondary schools; school proper names remain in their source language.
    return [
        convert(r) for r in rows if r.get("SCHUL_KND_SC_NM") in ("중학교", "고등학교")
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output")
    parser.add_argument("--region")
    args = parser.parse_args()
    key = os.environ.get("NEIS_API_KEY")
    if not key:
        parser.error("Set NEIS_API_KEY in the environment")
    try:
        rows = fetch(key, args.region)
        if not rows:
            raise RuntimeError("No secondary schools returned")
        Path(args.output).write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n"
        )
        print(
            f"Wrote {len(rows)} schools. Review the file, then run manage.py import-schools."
        )
    except Exception as error:
        # Avoid urllib exceptions exposing an API-key-bearing URL.
        raise SystemExit(
            "Import failed ("
            + type(error).__name__
            + "). Check connectivity, API access and response format."
        )
