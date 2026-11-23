"""Serve a Feed-Push-compatible RSS feed or publish a single poll as XML."""

import argparse
import logging
import os
import re
import signal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

from stock import DEFAULT_WATCH, MARKETS, load_state, poll, watch_list, write_atomic

PRODUCT_PAGES = {
    "eu:24ska012-sgp": "https://eco.ovhcloud.com/en-ie/kimsufi/ks-a/",
    "eu:24sk40-v1": "https://eco.ovhcloud.com/en-ie/kimsufi/ks-4/",
    "eu:27skle01-v1": "https://eco.ovhcloud.com/en-ie/kimsufi/ks-le-1/",
    "eu:27skle03-v1": "https://eco.ovhcloud.com/en-ie/kimsufi/ks-le-3/",
    "us:24sk40-v1-us": "https://eco.us.ovhcloud.com/kimsufi/ks-4/",
    "us:24sk50-v1-us": "https://eco.us.ovhcloud.com/kimsufi/ks-5/",
    "us:26sk50b-v1-us": "https://eco.us.ovhcloud.com/kimsufi/ks-5-b/",
}


def item_link(entry):
    watch = entry.get("watch")
    if watch is None:
        legacy = re.match(r"API 区域 ([A-Z]+)｜套餐 ([\w-]+)｜", entry["description"])
        if legacy:
            market, plan = legacy.groups()
            watch = f"{market.lower()}:{plan}"
    return PRODUCT_PAGES.get(watch, entry["link"])


def rss_xml(items):
    root = ET.Element("rss", version="2.0")
    channel = ET.SubElement(root, "channel")
    ET.SubElement(channel, "title").text = "OVH 独立服务器补货"
    ET.SubElement(channel, "link").text = MARKETS["eu"][1]
    ET.SubElement(channel, "description").text = "OVH 公开库存接口报告的套餐、配置和机房补货事件"
    ET.SubElement(channel, "language").text = "zh-CN"
    for entry in items:
        item = ET.SubElement(channel, "item")
        for tag, value in (
            ("title", entry["title"]),
            ("link", item_link(entry)),
            ("description", entry["description"]),
            ("pubDate", entry["pubDate"]),
        ):
            ET.SubElement(item, tag).text = value
        ET.SubElement(item, "guid", isPermaLink="false").text = entry["guid"]
    ET.indent(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def serve(state_path, refresh, interval, port):
    stop = Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_feed(include_body=True)

        def do_HEAD(self):
            self.send_feed(include_body=False)

        def send_feed(self, include_body):
            if urlsplit(self.path).path != "/rss.xml":
                self.send_error(404)
                return
            try:
                state = load_state(state_path)
            except (OSError, ValueError):
                logging.exception("Cannot read feed state")
                self.send_error(503)
                return
            body = rss_xml(state["items"])
            self.send_response(200)
            self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            if include_body:
                self.wfile.write(body)

    def poll_loop():
        while not stop.is_set():
            try:
                refresh()
            except (OSError, ValueError):
                logging.exception("Cannot update feed state")
            stop.wait(interval)

    def shutdown(*_):
        stop.set()
        Thread(target=server.shutdown, daemon=True).start()

    with ThreadingHTTPServer(("0.0.0.0", port), Handler) as server:
        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)
        Thread(target=poll_loop, daemon=True).start()
        logging.info("RSS listening on port %d at /rss.xml", port)
        server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", type=Path, metavar="RSS_FILE", help="poll once and write an RSS file")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        watches = watch_list(os.getenv("OVH_WATCH") or DEFAULT_WATCH)
        datacenters = set(os.getenv("OVH_DATACENTERS", "").lower().replace(",", " ").split())
        interval = int(os.getenv("POLL_SECONDS", "60"))
        port = int(os.getenv("PORT", "8787"))
        if interval < 15 or not 1 <= port <= 65535:
            raise ValueError("POLL_SECONDS must be at least 15 and PORT must be 1–65535")
    except ValueError as exc:
        parser.error(str(exc))
    state_path = Path(os.getenv("DATA_DIR", "/data")) / "state.json"

    def refresh():
        return poll(state_path, watches, datacenters)

    if args.once:
        if not refresh():
            parser.exit(1, "All OVH inventory requests failed. The existing RSS was preserved.\n")
        write_atomic(args.once, rss_xml(load_state(state_path)["items"]))
    else:
        serve(state_path, refresh, interval, port)


if __name__ == "__main__":
    main()
