"""SSRF protection guard for LibreCrawl.

Provides connect-time validation for outgoing HTTP/HTTPS connections to prevent
Server-Side Request Forgery (SSRF) to private, local, loopback, link-local,
multicast, reserved, and non-globally-routable addresses.

Validates the actual peer socket IP at connect time, protecting against:
- Direct requests to private/internal IPs
- HTTP redirects (301/302/307/308) to internal IPs
- DNS rebinding attacks (time-of-check to time-of-use IP changes)
- IPv4-mapped and IPv4-compatible IPv6 bypasses
"""
import ipaddress
import os
import socket
from typing import Any, Callable, Iterable, Optional, Union
from urllib.parse import urlparse

import requests
import requests.adapters
from requests.adapters import DEFAULT_POOLBLOCK, HTTPAdapter
import urllib3
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.poolmanager import PoolManager, ProxyManager


class BlockedDestinationError(requests.exceptions.ConnectionError):
    """Raised when an outgoing connection attempts to connect to a blocked IP."""

    def __init__(self, host: str, ip: str, port: Optional[int] = None):
        self.host = host
        self.ip = ip
        self.port = port
        port_suffix = f":{port}" if port is not None else ""
        self.message = f"Access to {host}{port_suffix} ({ip}) is blocked by SSRF policy"
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message


def is_blocked_ip(ip: Union[str, bytes, bytearray, ipaddress.IPv4Address, ipaddress.IPv6Address]) -> bool:
    """Determine whether an IP address is blocked under SSRF policy.

    Blocked addresses include:
    - Loopback (127.0.0.0/8, ::1)
    - RFC1918 private IPv4 networks (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
    - Link-local (169.254.0.0/16, fe80::/10)
    - Carrier-Grade NAT (CGNAT) 100.64.0.0/10
    - Unspecified / current network (0.0.0.0/8, ::)
    - Multicast (224.0.0.0/4, ff00::/8)
    - Reserved / future use (240.0.0.0/4, etc.)
    - IPv6 Unique Local Addresses (ULA) fc00::/7
    - IPv4-mapped IPv6 (::ffff:x.x.x.x) where mapped IPv4 is blocked
    - IPv4-compatible IPv6 (::x.x.x.x) where compatible IPv4 is blocked
    - 6to4 prefix (2002::/16) where embedded IPv4 is blocked

    Returns True if blocked, False if globally routable.
    """
    if isinstance(ip, (bytes, bytearray)):
        ip = ip.decode('utf-8', errors='replace')
    if isinstance(ip, str):
        # Strip brackets from IPv6 host strings like [::1]
        ip = ip.strip('[]')
        # Strip scope id if present, e.g. fe80::1%eth0
        if '%' in ip:
            ip = ip.split('%', 1)[0]
        ip = ipaddress.ip_address(ip)

    if isinstance(ip, ipaddress.IPv6Address):
        # Explicit handling for IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1)
        if ip.ipv4_mapped is not None:
            return is_blocked_ip(ip.ipv4_mapped)

        # Deprecated IPv4-compatible IPv6 (::x.x.x.x) where high 96 bits are 0
        int_val = int(ip)
        if (int_val >> 32) == 0 and int_val > 1:
            return is_blocked_ip(ipaddress.IPv4Address(int_val & 0xffffffff))

        # 6to4 encapsulation (2002::/16) embedding an IPv4 in the next 32 bits
        if ip in ipaddress.IPv6Network('2002::/16'):
            v4_int = (int_val >> 80) & 0xffffffff
            if is_blocked_ip(ipaddress.IPv4Address(v4_int)):
                return True

    return not ip.is_global


# Global test hooks for test-only allowlisting
_test_allowlist: set = set()
_test_allow_hook: Optional[Callable[[str, str, Optional[int]], bool]] = None


def set_test_allowlist(items: Iterable[Any]) -> None:
    """Set global test allowlist (test-only helper)."""
    global _test_allowlist
    _test_allowlist = set(items)


def clear_test_allowlist() -> None:
    """Clear global test allowlist and hook (test-only helper)."""
    global _test_allowlist, _test_allow_hook
    _test_allowlist = set()
    _test_allow_hook = None


def set_test_allow_hook(hook: Optional[Callable[[str, str, Optional[int]], bool]]) -> None:
    """Set global test allow hook callback: (host, ip, port) -> bool."""
    global _test_allow_hook
    _test_allow_hook = hook


def is_allowed_by_test_hook(
    host: str,
    ip: str,
    port: Optional[int] = None,
    instance_hook: Optional[Callable[[str, str, Optional[int]], bool]] = None,
    instance_allowlist: Optional[Iterable[Any]] = None,
) -> bool:
    """Check whether a target is permitted by a test-only allowlist or hook."""
    if instance_hook and instance_hook(host, ip, port):
        return True
    if _test_allow_hook and _test_allow_hook(host, ip, port):
        return True

    # Check instance allowlist
    if instance_allowlist is not None:
        inst_set = set(instance_allowlist)
        if ip in inst_set or host in inst_set:
            return True
        if port is not None:
            if (ip, port) in inst_set or (host, port) in inst_set:
                return True
            if f"{ip}:{port}" in inst_set or f"{host}:{port}" in inst_set:
                return True

    # Check global test allowlist
    if _test_allowlist:
        if ip in _test_allowlist or host in _test_allowlist:
            return True
        if port is not None:
            if (ip, port) in _test_allowlist or (host, port) in _test_allowlist:
                return True
            if f"{ip}:{port}" in _test_allowlist or f"{host}:{port}" in _test_allowlist:
                return True

    return False


def is_private_allowed(allow_override: Optional[Any] = None) -> bool:
    """Check if private targets are permitted (opt-out active)."""
    if allow_override is not None:
        if callable(allow_override):
            allow_override = allow_override()
        if allow_override is not None:
            return bool(allow_override)
    return os.getenv('ALLOW_PRIVATE_TARGETS', '').lower() in ('true', '1', 'yes')


def check_target_url(url: str, allow_private_targets: Optional[Any] = None) -> tuple[bool, str]:
    """Validate a target URL host before initiating a crawl.

    Provides early user-facing feedback for start URLs.
    Returns (is_blocked, error_message).
    """
    if is_private_allowed(allow_private_targets):
        return False, ""

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return True, f"Cannot parse valid host from URL: {url}"

        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        clean_host = hostname.strip('[]')

        # Check if hostname itself is already an IP address
        try:
            if is_blocked_ip(clean_host):
                if is_allowed_by_test_hook(hostname, clean_host, port):
                    return False, ""
                return True, f"Host '{hostname}' is a blocked private/reserved IP"
            return False, ""
        except ValueError:
            pass

        # Hostname is a domain name: resolve DNS
        try:
            addrs = socket.getaddrinfo(hostname, port)
        except socket.gaierror as e:
            return True, f"Could not resolve host '{hostname}': {e}"

        for addr in addrs:
            sockaddr = addr[4]
            ip_str = sockaddr[0]
            if is_allowed_by_test_hook(hostname, ip_str, port):
                continue
            if is_blocked_ip(ip_str):
                return True, f"Host '{hostname}' resolves to blocked private/reserved IP: {ip_str}"

        return False, ""
    except Exception as e:
        return True, f"Error validating URL '{url}': {e}"


def find_blocked_destination_error(exc: BaseException) -> Optional[BlockedDestinationError]:
    """Inspect an exception or exception tree to unwrap any underlying BlockedDestinationError."""
    seen = set()
    stack = [exc]
    while stack:
        cur = stack.pop()
        if cur is None or id(cur) in seen:
            continue
        seen.add(id(cur))
        if isinstance(cur, BlockedDestinationError):
            return cur
        if isinstance(cur, BaseException):
            if cur.__cause__:
                stack.append(cur.__cause__)
            if cur.__context__:
                stack.append(cur.__context__)
            if hasattr(cur, 'args'):
                for arg in cur.args:
                    if isinstance(arg, BaseException):
                        stack.append(arg)
                    elif isinstance(arg, (list, tuple)):
                        for item in arg:
                            if isinstance(item, BaseException):
                                stack.append(item)
            if hasattr(cur, 'reason'):
                stack.append(cur.reason)
    return None


class _GuardedConnectionMixin:
    """Mixin for urllib3 connection classes to enforce SSRF validation upon socket connect."""

    allow_private_targets: Any = None
    test_allowlist: Any = None
    test_allow_hook: Any = None

    def _new_conn(self) -> socket.socket:
        sock = super()._new_conn()
        try:
            peer = sock.getpeername()
            peer_ip = peer[0]
            peer_port = peer[1] if len(peer) > 1 else self.port
        except Exception:
            sock.close()
            raise

        allow_flag = getattr(self, 'allow_private_targets', None)
        if not is_private_allowed(allow_flag):
            hook = getattr(self, 'test_allow_hook', None)
            allowlist = getattr(self, 'test_allowlist', None)
            if not is_allowed_by_test_hook(self.host, peer_ip, peer_port, hook, allowlist):
                if is_blocked_ip(peer_ip):
                    sock.close()
                    raise BlockedDestinationError(self.host, peer_ip, peer_port)

        return sock


class GuardedHTTPConnection(_GuardedConnectionMixin, HTTPConnection):
    pass


class GuardedHTTPSConnection(_GuardedConnectionMixin, HTTPSConnection):
    pass


class GuardedHTTPConnectionPool(HTTPConnectionPool):
    ConnectionCls = GuardedHTTPConnection

    def _new_conn(self) -> GuardedHTTPConnection:
        conn = super()._new_conn()
        conn.allow_private_targets = getattr(self, 'allow_private_targets', None)
        conn.test_allowlist = getattr(self, 'test_allowlist', None)
        conn.test_allow_hook = getattr(self, 'test_allow_hook', None)
        return conn


class GuardedHTTPSConnectionPool(HTTPSConnectionPool):
    ConnectionCls = GuardedHTTPSConnection

    def _new_conn(self) -> GuardedHTTPSConnection:
        conn = super()._new_conn()
        conn.allow_private_targets = getattr(self, 'allow_private_targets', None)
        conn.test_allowlist = getattr(self, 'test_allowlist', None)
        conn.test_allow_hook = getattr(self, 'test_allow_hook', None)
        return conn


class GuardedPoolManager(PoolManager):
    """PoolManager that wires guarded HTTP/HTTPS connection pools."""

    def __init__(
        self,
        *args,
        allow_private_targets: Optional[Any] = None,
        test_allowlist: Optional[Any] = None,
        test_allow_hook: Optional[Any] = None,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.allow_private_targets = allow_private_targets
        self.test_allowlist = test_allowlist
        self.test_allow_hook = test_allow_hook
        self.pool_classes_by_scheme['http'] = GuardedHTTPConnectionPool
        self.pool_classes_by_scheme['https'] = GuardedHTTPSConnectionPool

    def _new_pool(self, scheme, host, port, request_context=None):
        pool = super()._new_pool(scheme, host, port, request_context=request_context)
        pool.allow_private_targets = self.allow_private_targets
        pool.test_allowlist = self.test_allowlist
        pool.test_allow_hook = self.test_allow_hook
        return pool


class GuardedProxyManager(ProxyManager):
    """ProxyManager that wires guarded connection pools.

    Note on Proxies:
    When an HTTP(S) proxy is configured, the socket connection established by the client
    is made directly to the proxy server itself. The connect-time check validates the
    peer address of that connection (the proxy hop). If connecting through an internal or
    local proxy (e.g. 127.0.0.1 or RFC1918 proxy), set ALLOW_PRIVATE_TARGETS=true.
    """

    def __init__(
        self,
        *args,
        allow_private_targets: Optional[Any] = None,
        test_allowlist: Optional[Any] = None,
        test_allow_hook: Optional[Any] = None,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.allow_private_targets = allow_private_targets
        self.test_allowlist = test_allowlist
        self.test_allow_hook = test_allow_hook
        self.pool_classes_by_scheme['http'] = GuardedHTTPConnectionPool
        self.pool_classes_by_scheme['https'] = GuardedHTTPSConnectionPool

    def _new_pool(self, scheme, host, port, request_context=None):
        pool = super()._new_pool(scheme, host, port, request_context=request_context)
        pool.allow_private_targets = self.allow_private_targets
        pool.test_allowlist = self.test_allowlist
        pool.test_allow_hook = self.test_allow_hook
        return pool


class GuardedHTTPAdapter(HTTPAdapter):
    """Requests HTTPAdapter providing connect-time SSRF validation."""

    def __init__(
        self,
        *args,
        allow_private_targets: Optional[Any] = None,
        test_allowlist: Optional[Any] = None,
        test_allow_hook: Optional[Any] = None,
        **kwargs
    ):
        self.allow_private_targets = allow_private_targets
        self.test_allowlist = test_allowlist
        self.test_allow_hook = test_allow_hook
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, connections, maxsize, block=DEFAULT_POOLBLOCK, **pool_kwargs):
        self._pool_connections = connections
        self._pool_maxsize = maxsize
        self._pool_block = block
        self.poolmanager = GuardedPoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            allow_private_targets=self.allow_private_targets,
            test_allowlist=self.test_allowlist,
            test_allow_hook=self.test_allow_hook,
            **pool_kwargs,
        )

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        if proxy in self.proxy_manager:
            return self.proxy_manager[proxy]
        if proxy.lower().startswith("socks"):
            return super().proxy_manager_for(proxy, **proxy_kwargs)

        proxy_headers = self.proxy_headers(proxy)
        manager = self.proxy_manager[proxy] = GuardedProxyManager(
            proxy,
            proxy_headers=proxy_headers,
            num_pools=self._pool_connections,
            maxsize=self._pool_maxsize,
            block=self._pool_block,
            allow_private_targets=self.allow_private_targets,
            test_allowlist=self.test_allowlist,
            test_allow_hook=self.test_allow_hook,
            **proxy_kwargs,
        )
        return manager

    def send(self, request, *args, **kwargs):
        try:
            return super().send(request, *args, **kwargs)
        except Exception as e:
            blocked_err = find_blocked_destination_error(e)
            if blocked_err is not None:
                raise blocked_err from e
            raise


def mount_guarded_adapter(
    session: requests.Session,
    pool_connections: int = 10,
    pool_maxsize: int = 10,
    max_retries: int = 0,
    allow_private_targets: Optional[Any] = None,
    test_allowlist: Optional[Any] = None,
    test_allow_hook: Optional[Any] = None,
) -> GuardedHTTPAdapter:
    """Mount GuardedHTTPAdapter onto http:// and https:// on the given session."""
    adapter = GuardedHTTPAdapter(
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize,
        max_retries=max_retries,
        allow_private_targets=allow_private_targets,
        test_allowlist=test_allowlist,
        test_allow_hook=test_allow_hook,
    )
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return adapter


def make_guarded_session(
    pool_connections: int = 10,
    pool_maxsize: int = 10,
    max_retries: int = 0,
    allow_private_targets: Optional[Any] = None,
    test_allowlist: Optional[Any] = None,
    test_allow_hook: Optional[Any] = None,
) -> requests.Session:
    """Create and return a new requests.Session equipped with connect-time SSRF guards."""
    session = requests.Session()
    mount_guarded_adapter(
        session,
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize,
        max_retries=max_retries,
        allow_private_targets=allow_private_targets,
        test_allowlist=test_allowlist,
        test_allow_hook=test_allow_hook,
    )
    return session
