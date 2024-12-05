import feedparser
import urllib.parse
import requests
import os
import re
import time
import json
import urllib3
import logging
import random
import signal
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse
from typing import Dict, Optional, Set, List, Tuple

# 禁用不安全请求的警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置日志格式
logging.basicConfig(
    format='%(message)s',
    level=logging.INFO
)

# 配置
CONFIG = {
    "use_proxy": "yes",  # 是否使用代理 "yes" 或 "no"
    "proxy_interval": 120,  # 代理模式检查间隔(秒)
    "local_interval": 300,  # 本地模式检查间隔(秒)
    "max_retries": 1,  # 最大重试次数
    "proxy_file": "./local_proxies.txt",
    "bark_url": "https://bark.suiyi.de/TjqwSqh5ooah4zrFZL63qR"
}

RSS_SOURCES = [
    {
        "url": "https://rss.nodeseek.com/",
        "keywords": ["咸鱼云", "白丝云"],
        "group": "?group=Nodeseek",
        "cache_file": "./cache_nodeseek.json"
    },
    {
        "url": "http://www.v2ex.com/index.xml",
        "keywords": ["咸鱼云", "白丝云"],
        "group": "?group=Hezu",
        "cache_file": "./cache_v2ex.json"
    }
]

# 全局变量用于控制程序退出
running = True


@dataclass
class ProxyState:
    """代理状态记录"""
    last_used: Dict[str, datetime] = None  # 每个域名的最后使用时间
    fail_count: Dict[str, int] = None  # 每个域名的失败次数
    success_count: Dict[str, int] = None  # 每个域名的成功次数

    def __init__(self):
        self.last_used = {}
        self.fail_count = {}
        self.success_count = {}


class ProxyManager:
    def __init__(self, cooldown: int = 300):
        self.proxy_states: Dict[str, ProxyState] = {}
        self.cooldown = cooldown
        self.current_indexes: Dict[str, int] = {}

    def clean_invalid_proxies(self, current_proxies: List[str]) -> None:
        """清理已不存在的代理状态"""
        invalid_proxies = [proxy for proxy in list(self.proxy_states.keys())
                           if proxy not in current_proxies]
        for proxy in invalid_proxies:
            del self.proxy_states[proxy]

    def get_domain(self, url: str) -> str:
        return urlparse(url).netloc

    def _get_or_create_state(self, proxy: str) -> ProxyState:
        """获取或创建代理状态"""
        return self.proxy_states.setdefault(proxy, ProxyState())

    def can_use_proxy(self, proxy: str, domain: str) -> bool:
        state = self._get_or_create_state(proxy)

        if domain in state.last_used:
            time_since_last_use = (datetime.now() - state.last_used[domain]).total_seconds()
            if time_since_last_use < self.cooldown:
                return False

            if state.fail_count.get(domain, 0) >= 3:
                if time_since_last_use >= self.cooldown * 2:
                    state.fail_count[domain] = 0
                    return True
                return False

        return True

    def select_proxy(self, url: str, proxies: List[str]) -> Optional[str]:
        if not proxies:
            return None

        # 清理不存在的代理状态
        self.clean_invalid_proxies(proxies)

        domain = self.get_domain(url)
        current_index = self.current_indexes.get(domain, -1)
        available_proxies = [p for p in proxies if self.can_use_proxy(p, domain)]

        if available_proxies:
            current_index = (current_index + 1) % len(proxies)
            self.current_indexes[domain] = current_index
            return available_proxies[current_index % len(available_proxies)]

        return min(proxies,
                   key=lambda p: self._get_or_create_state(p).last_used.get(domain, datetime.min))

    def update_proxy_result(self, url: str, proxy: str, success: bool) -> None:
        domain = self.get_domain(url)
        state = self._get_or_create_state(proxy)
        state.last_used[domain] = datetime.now()

        if success:
            state.success_count[domain] = state.success_count.get(domain, 0) + 1
            state.fail_count[domain] = 0
        else:
            state.fail_count[domain] = state.fail_count.get(domain, 0) + 1

    def get_proxy_stats(self) -> str:
        """获取代理状态统计"""
        stats = ["代理状态统计:"]
        for proxy, state in self.proxy_states.items():
            stats.append(f"代理: {proxy}")
            for domain in state.last_used.keys():
                time_ago = (datetime.now() - state.last_used[domain]).total_seconds()
                stats.append(f"最后使用: {time_ago:.0f}秒前   访问域名为{domain}")

        return "\n".join(stats)


def signal_handler(signum, frame):
    """信号处理函数"""
    global running
    logging.info('接收到退出信号，准备安全退出...')
    running = False


def load_proxies() -> list:
    """加载代理列表"""
    try:
        if os.path.exists(CONFIG["proxy_file"]):
            with open(CONFIG["proxy_file"], "r") as f:
                # 读取所有行并过滤空行
                proxies = [line.strip() for line in f if line.strip()]
                return proxies
        return []
    except Exception as e:
        logging.error(f"加载代理列表失败: {e}")
        return []


def match_keywords(text: str, pattern: str) -> bool:
    """匹配关键词"""
    try:
        if pattern.startswith('+'):
            terms = pattern.split('+')[1:]
            include_terms = [t for t in terms if not t.startswith('-')]
            exclude_terms = [t[1:] for t in terms if t.startswith('-')]

            return (
                    all(re.search(f".*{re.escape(term)}.*", text, re.I) for term in include_terms) and
                    not any(re.search(f".*{re.escape(term)}.*", text, re.I) for term in exclude_terms)
            )
        else:
            return bool(re.search(f".*{re.escape(pattern)}.*", text, re.I))
    except Exception as e:
        logging.error(f"正则匹配错误: {e}")
        return False


def load_cache(cache_file: str) -> Set[str]:
    """加载缓存"""
    try:
        if os.path.exists(cache_file):
            with open(cache_file, "r") as f:
                return set(json.load(f))
        return set()
    except Exception as e:
        logging.error(f"加载缓存失败: {e}")
        return set()


def save_cache(cache_file: str, cache: Set[str]) -> None:
    """保存缓存"""
    try:
        with open(cache_file, "w") as f:
            json.dump(list(cache), f)
    except Exception as e:
        logging.error(f"保存缓存失败: {e}")


def fetch_rss(url: str, proxy: Optional[str] = None) -> Optional[feedparser.FeedParserDict]:
    """抓取 RSS 源并解析"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Accept": "application/xml, application/rss+xml, text/xml, */*"
    }

    try:
        with requests.Session() as session:
            # 添加 http:// 前缀
            if proxy and not proxy.startswith('http'):
                proxy = f'http://{proxy}'
            proxies = {"http": proxy, "https": proxy} if proxy else None

            response = session.get(
                url,
                headers=headers,
                proxies=proxies,
                timeout=10,
                verify=False
            )
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            return feed if feed.entries else None
    except Exception as e:
        logging.error(f"[{url.split('//')[-1]}] 抓取失败: {str(e)}")
        return None


def push_notification(title: str, link: str, group: str) -> None:
    """发送通知"""
    try:
        push_content = link
        encoded_title = urllib.parse.quote(title, safe="")
        encoded_content = urllib.parse.quote(push_content, safe="")
        push_url = f"{CONFIG['bark_url']}/{encoded_title}/{encoded_content}{group}"

        response = requests.get(push_url, timeout=10)
        if response.status_code == 200:
            logging.info(f"推送成功: {title}")
        else:
            logging.error(f"推送失败: {title}. 响应: {response.text}")
    except Exception as e:
        logging.error(f"推送失败: {title} - {str(e)}")


def process_feed_entries(entries: list, source: dict) -> None:
    """处理RSS条目"""
    cached_guids = load_cache(source['cache_file'])
    new_guids = set()

    for entry in entries:
        guid = getattr(entry, 'id', entry.link)
        if guid in cached_guids:
            continue

        title = entry.title
        link = getattr(entry, 'link', "No link available.")

        for keyword in source['keywords']:
            if match_keywords(title, keyword):
                push_notification(title, link, source['group'])
                break

        new_guids.add(guid)

    save_cache(source['cache_file'], cached_guids | new_guids)


def check_rss_source(source: dict, proxies: list, proxy_manager: ProxyManager) -> None:
    """检查单个RSS源"""
    source_url = source['url']
    display_url = source_url.split('//')[-1]

    if CONFIG['use_proxy'].lower() == "yes":
        for attempt in range(CONFIG['max_retries']):
            if not running:
                return

            proxy = proxy_manager.select_proxy(source_url, proxies)
            if not proxy:
                logging.error("无可用代理")
                return

            logging.info(f"[{display_url}] 尝试 {attempt + 1}/{CONFIG['max_retries']} - 代理: {proxy}")
            feed = fetch_rss(source_url, proxy)
            success = bool(feed and feed.entries)

            proxy_manager.update_proxy_result(source_url, proxy, success)

            if success:
                process_feed_entries(feed.entries, source)
                logging.info(f"[{display_url}] 成功获取 {len(feed.entries)} 条")
                return

            logging.error(f"[{display_url}] 使用代理 {proxy} 获取失败")
            time.sleep(2)

        logging.error(f"[{display_url}] 全部尝试失败")
    else:
        logging.info(f"[{display_url}] 使用本机IP尝试获取")
        feed = fetch_rss(source_url)

        if feed and feed.entries:
            process_feed_entries(feed.entries, source)
            logging.info(f"[{display_url}] 成功获取 {len(feed.entries)} 条")
        else:
            logging.error(f"[{display_url}] 获取失败")


def main():
    """主函数"""
    proxy_manager = ProxyManager(cooldown=300)  # 5分钟冷却时间
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logging.info("RSS监控启动")
    logging.info(f"当前模式: {'使用代理' if CONFIG['use_proxy'].lower() == 'yes' else '使用本机IP'}")

    while running:
        try:
            proxies = load_proxies() if CONFIG['use_proxy'].lower() == "yes" else []
            if CONFIG['use_proxy'].lower() == "yes" and not proxies:
                logging.warning("无可用代理，等待下次检查...")
                time.sleep(CONFIG['proxy_interval'])
                continue

            if CONFIG['use_proxy'].lower() == "yes":
                logging.info(f"当前代理数量: {len(proxies)}")
                logging.info("\n" + proxy_manager.get_proxy_stats())

            for source in RSS_SOURCES:
                try:
                    check_rss_source(source, proxies, proxy_manager)
                except Exception as e:
                    logging.error(f"检查失败: {source['url']} - {str(e)}")

                if not running:
                    break

            if running:
                interval = CONFIG['proxy_interval'] if CONFIG['use_proxy'].lower() == "yes" else CONFIG['local_interval']
                logging.info(f"完成检查，等待 {interval} 秒后进行下次检查...")
                time.sleep(interval)

        except Exception as e:
            logging.error(f"运行错误: {str(e)}")
            interval = CONFIG['proxy_interval'] if CONFIG['use_proxy'].lower() == "yes" else CONFIG['local_interval']
            time.sleep(interval)

    logging.info("程序已安全退出")


if __name__ == "__main__":
    main()
