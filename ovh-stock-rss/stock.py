"""Poll OVH's public availability API and record restock events."""

import json
import logging
import os
import re
import tempfile
from email.utils import formatdate
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

MARKETS = {
    "eu": ("https://eu.api.ovh.com/1.0", "https://eco.ovhcloud.com/en-ie/"),
    "ca": ("https://ca.api.ovh.com/1.0", "https://eco.ovhcloud.com/en-ca/"),
    "us": ("https://api.us.ovhcloud.com/1.0", "https://us.ovhcloud.com/bare-metal/"),
}
DEFAULT_WATCH = "eu:24ska01,eu:24sk40,eu:27skle03-v1"
PLAN_NAMES = {"24ska01": "KS-A", "24sk40": "KS-4", "27skle03-v1": "KS-LE-3"}
IN_STOCK = re.compile(r"(?:available|[0-9]+[HD](?:-high|-low)?)", re.I)


def watch_list(value):
    watches = list(dict.fromkeys(part.strip().lower() for part in value.split(",")))
    for watch in watches:
        market, _, plan = watch.partition(":")
        if market not in MARKETS or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", plan):
            raise ValueError(f"Invalid OVH_WATCH entry {watch!r}. Expected eu, ca or us followed by :planCode.")
    return watches


def query_availability(market, plan):
    api, _ = MARKETS[market]
    query = urlencode({"planCode": plan})
    request = Request(
        f"{api}/dedicated/server/datacenter/availabilities?{query}",
        headers={"Accept": "application/json", "User-Agent": "Feed-Push-OVH-RSS/1.0"},
    )
    with urlopen(request, timeout=12) as response:
        return json.load(response)


def parse_availability(payload, plan, datacenters):
    if not isinstance(payload, list):
        raise ValueError("Expected a list of OVH stock configurations")
    in_stock, uncertain = {}, set()
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError("Invalid OVH stock configuration")
        if row.get("planCode") and row["planCode"] != plan:
            continue
        locations = row.get("datacenters")
        if not isinstance(locations, list):
            raise ValueError("Expected a list of OVH datacenters")
        memory, storage = row.get("memory") or "", row.get("storage") or ""
        config = row.get("fqn") or ""
        if not all(isinstance(field, str) for field in (config, memory, storage)):
            raise ValueError("Invalid OVH hardware configuration")
        for location in locations:
            if not isinstance(location, dict):
                raise ValueError("Invalid OVH datacenter")
            dc, status = location.get("datacenter"), location.get("availability")
            if not isinstance(dc, str) or not dc or not isinstance(status, str) or not status:
                raise ValueError("Invalid OVH datacenter or availability status")
            dc = dc.lower()
            if datacenters and dc not in datacenters:
                continue
            key = json.dumps([config, memory, storage, dc], separators=(",", ":"))
            if IN_STOCK.fullmatch(status):
                in_stock[key] = (dc, status, memory, storage, config)
            elif status.lower() not in {"unavailable", "comingsoon"}:
                uncertain.add(key)
    return in_stock, uncertain


def load_state(path):
    try:
        with path.open(encoding="utf-8") as stream:
            return json.load(stream)
    except FileNotFoundError:
        return {"stock": {}, "items": []}


def write_atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temp_path = Path(stream.name)
        try:
            stream.write(content)
            stream.close()
            os.replace(temp_path, path)
        finally:
            temp_path.unlink(missing_ok=True)


def poll(path, watches, datacenters, fetch=query_availability):
    state = load_state(path)
    snapshots = {}
    events, successes = [], 0
    for watch in watches:
        market, plan = watch.split(":")
        previous = set(state["stock"].get(watch, ()))
        try:
            current, uncertain = parse_availability(fetch(market, plan), plan, datacenters)
        except (OSError, ValueError) as exc:
            logging.warning("%s polling failed: %s", watch, exc)
            if watch in state["stock"]:
                snapshots[watch] = sorted(previous)
            continue
        successes += 1
        snapshots[watch] = sorted(current.keys() | (previous & uncertain))
        for key in sorted(current.keys() - previous):
            dc, status, memory, storage, config = current[key]
            events.append({
                "guid": f"urn:uuid:{uuid4()}",
                "title": f"OVH 补货 · {PLAN_NAMES.get(plan, plan.upper())} · {dc.upper()} · {status}",
                "description": (
                    f"API 区域 {market.upper()}｜套餐 {plan}｜机房 {dc.upper()}｜库存 {status}"
                    f"｜内存 {memory or '—'}｜硬盘 {storage or '—'}｜配置 {config or '—'}"
                ),
                "link": MARKETS[market][1],
                "pubDate": formatdate(usegmt=True),
            })
        logging.info("%s: %d available configurations", watch, len(current))
    if successes:
        new_state = {"stock": snapshots, "items": (events + state["items"])[:200]}
        if new_state != state:
            write_atomic(path, (json.dumps(new_state, ensure_ascii=False, indent=2) + "\n").encode())
    return successes
