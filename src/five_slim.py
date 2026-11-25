# -*- coding: utf-8 -*-
# 五大平台·外壳（极小）：真正逻辑运行时从远端拉取后加载，避免导入器体积限制
# 在线更新：源码放在远端，改完只需换下面的 _SRC，壳和 JSON 都不用重新导入
import time
import urllib.request

_SRC = "https://ghfast.top/https://raw.githubusercontent.com/gaijinxiang/wmz-five-src/main/src/five_full.py"
# 备用镜像：主地址挂了/过期就依次尝试
_MIRRORS = [
    _SRC,
    "https://gh-proxy.com/https://raw.githubusercontent.com/gaijinxiang/wmz-five-src/main/src/five_full.py",
    "https://ghproxy.net/https://raw.githubusercontent.com/gaijinxiang/wmz-five-src/main/src/five_full.py",
]
_NS = {}
_CODE = {}


def _fetch(url):
    for u in (url, url + ("&" if "?" in url else "?") + "t=%d" % int(time.time())):
        try:
            req = urllib.request.Request(u, headers={
                "User-Agent": "okhttp/3.12.0",
                "Accept": "*/*",
            })
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
            if raw and len(raw) > 2000:
                return raw.decode("utf-8", "ignore")
        except Exception:
            continue
    return ""


def _load():
    if _NS.get("Spider"):
        return _NS["Spider"]
    if not _CODE.get("txt"):
        for u in _MIRRORS:
            txt = _fetch(u)
            if txt and "class Spider" in txt:
                _CODE["txt"] = txt
                break
    if not _CODE.get("txt"):
        raise RuntimeError("五大平台源码拉取失败，检查网络或换备用地址")
    ns = {"__name__": "five_remote", "__file__": __file__}
    exec(compile(_CODE["txt"], "five_remote.py", "exec"), ns)
    _NS.update(ns)
    return ns["Spider"]


class Spider(object):
    def __init__(self):
        self._o = None

    def _impl(self):
        if self._o is None:
            self._o = _load()()
        return self._o

    def init(self, extend=""):
        self._ext = extend
        self._impl().init(extend)
        # 外层兜底：把 ext 里的夸克 Cookie 直接写进远端模块的全局变量，
        # 避免内层 init 的 global 赋值在某些执行环境里不生效。
        try:
            import json as _j
            _e = extend if isinstance(extend, dict) else (
                _j.loads(extend) if str(extend).strip().startswith("{") else {})
            _ck = str(_e.get("quark_cookie") or "").strip()
            if _ck:
                _NS["_SITE_QUARK_COOKIE"] = " ".join(_ck.split())
        except Exception:
            pass

    def homeContent(self, filter):
        return self._impl().homeContent(filter)

    def homeVideoContent(self):
        return self._impl().homeVideoContent()

    def categoryContent(self, tid, pg, filter, extend):
        return self._impl().categoryContent(tid, pg, filter, extend)

    def searchContent(self, key, quick, pg="1"):
        return self._impl().searchContent(key, quick, pg)

    def detailContent(self, ids):
        return self._impl().detailContent(ids)

    def playerContent(self, flag, pid, vipFlags):
        return self._impl().playerContent(flag, pid, vipFlags)

    def localProxy(self, param):
        try:
            return self._impl().localProxy(param)
        except Exception:
            return [404, "text/plain", b"not found", {}]

    def action(self, action):
        return None
