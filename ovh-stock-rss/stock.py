"""Poll OVH's public availability API and record restock events."""

import json
import logging
import os
import re
import tempfile
from email.utils import formatdate
from functools import lru_cache
from pathlib import Path
from time import monotonic
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

MARKETS = {
    "eu": ("https://eu.api.ovh.com/1.0", "https://eco.ovhcloud.com/en-ie/"),
    "ca": ("https://ca.api.ovh.com/1.0", "https://eco.ovhcloud.com/en-ca/"),
    "us": ("https://api.us.ovhcloud.com/1.0", "https://us.ovhcloud.com/bare-metal/"),
}
SUBSIDIARIES = {"eu": "IE", "ca": "CA", "us": "US"}
BARE_METAL_PAGES = {
    "eu": "https://www.ovhcloud.com/en-ie/bare-metal/",
    "ca": "https://www.ovhcloud.com/en-ca/bare-metal/",
    "us": MARKETS["us"][1],
}
DEFAULT_WATCH = "eu:24ska012-sgp,eu:24sk40-v1,eu:27skle01-v1,eu:27skle03-v1"
IN_STOCK = re.compile(r"(?:available|[0-9]+[HD](?:-high|-low)?)", re.I)


def watch_list(value):
    watches = list(dict.fromkeys(part.strip().lower() for part in value.split(",")))
    for watch in watches:
        market, _, plan = watch.partition(":")
        if market not in MARKETS or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", plan):
            raise ValueError(f"Invalid OVH_WATCH entry {watch!r}. Expected eu, ca or us followed by :planCode.")
    return watches


def public_json(market, path, **params):
    api, _ = MARKETS[market]
    request = Request(
        f"{api}/{path}?{urlencode(params)}",
        headers={"Accept": "application/json", "User-Agent": "Feed-Push-OVH-RSS/1.0"},
    )
    with urlopen(request, timeout=12) as response:
        return json.load(response)


def query_availability(market, plan):
    return public_json(market, "dedicated/server/datacenter/availabilities", planCode=plan)


@lru_cache(maxsize=12)
def catalog_plans(market, product, hour):
    payload = public_json(market, f"order/catalog/public/{product}", ovhSubsidiary=SUBSIDIARIES[market])
    if not isinstance(payload, dict) or not isinstance(payload.get("plans"), list):
        raise ValueError("Invalid OVH public catalog")
    return {plan["planCode"]: plan for plan in payload["plans"] if plan.get("planCode")}


def find_catalog_plan(market, plan):
    hour = int(monotonic() // 3600)
    for product in ("eco", "baremetalServers"):
        record = catalog_plans(market, product, hour).get(plan)
        if record:
            link = MARKETS[market][1] if product == "eco" else BARE_METAL_PAGES[market]
            return record, link
    return None, None


def addon_id(code, plan):
    code = code.lower()
    for suffix in (plan, plan.partition("-v")[0]):
        if code.endswith("-" + suffix):
            code = code.removesuffix("-" + suffix)
            break
    return tuple(part for part in code.split("-") if not re.fullmatch(r"ddr[0-9]+", part))


def matches_catalog(config, record, plan):
    addons = {family["name"]: family.get("addons") or [] for family in record.get("addonFamilies") or []}
    for name, code in zip(("memory", "storage"), config[2:4]):
        options = addons.get(name, [])
        if code and options and all(addon_id(code, plan) != addon_id(option, plan) for option in options):
            return False
    return True


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


def poll(path, watches, datacenters, fetch=query_availability, catalog=find_catalog_plan):
    state = load_state(path)
    snapshots = {}
    events, successes = [], 0
    for watch in watches:
        market, plan = watch.split(":")
        previous = set(state["stock"].get(watch, ()))
        try:
            current, uncertain = parse_availability(fetch(market, plan), plan, datacenters)
            record, link = catalog(market, plan) if current else (None, None)
            if current and not record:
                logging.info("%s: no matching plan in the public catalog", watch)
            current = {key: item for key, item in current.items() if record and matches_catalog(item, record, plan)}
        except (OSError, ValueError) as exc:
            logging.warning("%s polling failed: %s", watch, exc)
            if watch in state["stock"]:
                snapshots[watch] = sorted(previous)
            continue
        successes += 1
        snapshots[watch] = sorted(current.keys() | (previous & uncertain))
        for key in sorted(current.keys() - previous):
            dc, status, memory, storage, config = current[key]
            name = (record.get("invoiceName") or plan.upper()).partition(" | ")[0]
            events.append({
                "guid": f"urn:uuid:{uuid4()}",
                "watch": watch,
                "title": f"OVH 补货 · {name} · {dc.upper()} · {status}",
                "description": (
                    f"API 区域 {market.upper()}｜套餐 {plan}｜机房 {dc.upper()}｜库存 {status}"
                    f"｜内存 {memory or '—'}｜硬盘 {storage or '—'}｜配置 {config or '—'}"
                ),
                "link": link,
                "pubDate": formatdate(usegmt=True),
            })
        logging.info("%s: %d available configurations", watch, len(current))
    if successes:
        new_state = {"stock": snapshots, "items": (events + state["items"])[:200]}
        if new_state != state:
            write_atomic(path, (json.dumps(new_state, ensure_ascii=False, indent=2) + "\n").encode())
    return successes
