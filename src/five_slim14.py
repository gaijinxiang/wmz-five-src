# -*- coding: utf-8 -*-
# 五大平台·外壳（极小）：真正逻辑运行时从远端拉取后加载，避免导入器体积限制
# 在线更新：源码放在远端，改完只需换下面的 _SRC，壳和 JSON 都不用重新导入
import gzip
import json
import time
import urllib.request

_RAW = "https://raw.githubusercontent.com/gaijinxiang/wmz-five-src/main/src/five_full.py"
_GZ = "https://raw.githubusercontent.com/gaijinxiang/wmz-five-src/eede1d8cfabb8125ab259348b2938995039db9be/src/five_full.py.gz"
# 实测 ghfast 拉 1.4MB 要 20 秒以上，壳会判超时；gh-proxy 只要 3 秒，放第一位
_JP = "https://gcore.jsdelivr.net/gh/gaijinxiang/wmz-five-src@eede1d8cfabb8125ab259348b2938995039db9be/src/five_full.py.gz"
_SRC = _JP
_MIRRORS = [
    _JP,
    "https://testingcf.jsdelivr.net/gh/gaijinxiang/wmz-five-src@eede1d8cfabb8125ab259348b2938995039db9be/src/five_full.py.gz",
    "https://gh-proxy.com/" + _GZ,
    "https://ghfast.top/" + _GZ,
    "https://gh-proxy.com/" + _RAW,
    "https://ghfast.top/" + _RAW,
]

_SW_T = [0]
_SW_ON = [True]
_SW_URL = "https://gh-proxy.com/" + _RAW.replace("five_full.py", "switch.json")


def _sources_on():
    """总闸：switch.json 里 sources=0 时，整站直接返回空（所有页面打不开）"""
    try:
        if time.time() - _SW_T[0] > 60:
            _SW_T[0] = time.time()
            req = urllib.request.Request(_SW_URL + "?t=%d" % int(time.time()),
                                         headers={"User-Agent": "okhttp/3.12.0"})
            with urllib.request.urlopen(req, timeout=4) as r:
                obj = json.loads(r.read().decode("utf-8", "ignore"))
            if isinstance(obj, dict) and "sources" in obj:
                _SW_ON[0] = int(obj.get("sources")) != 0
    except Exception:
        pass
    return _SW_ON[0]

_NS = {}
_CODE = {}


def _fetch(url):
    for u in (url, url + ("&" if "?" in url else "?") + "t=%d" % int(time.time())):
        try:
            req = urllib.request.Request(u, headers={
                "User-Agent": "okhttp/3.12.0",
                "Accept": "*/*",
            })
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = r.read()
            if not raw or len(raw) < 200:
                continue
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)      # .gz 只有 500KB，2~3 秒能拉完
            txt = raw.decode("utf-8", "ignore")
            if "class Spider" in txt:
                return txt
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
        if not _sources_on():
            return {"class": [], "filters": {}}
        return self._impl().homeContent(filter)

    def homeVideoContent(self):
        if not _sources_on():
            return {"list": []}
        return self._impl().homeVideoContent()

    def categoryContent(self, tid, pg, filter, extend):
        if not _sources_on():
            return {"list": [], "page": 1, "pagecount": 1, "limit": 0, "total": 0}
        return self._impl().categoryContent(tid, pg, filter, extend)

    def searchContent(self, key, quick, pg="1"):
        if not _sources_on():
            return {"list": [], "page": 1, "pagecount": 1, "limit": 0, "total": 0}
        return self._impl().searchContent(key, quick, pg)

    def detailContent(self, ids):
        if not _sources_on():
            return {"list": []}
        return self._impl().detailContent(ids)

    def playerContent(self, flag, pid, vipFlags):
        if not _sources_on():
            return {"parse": 0, "jx": 0, "url": "", "msg": "源已关闭"}
        return self._impl().playerContent(flag, pid, vipFlags)

    def localProxy(self, param):
        try:
            return self._impl().localProxy(param)
        except Exception:
            return [404, "text/plain", b"not found", {}]

    def action(self, action):
        return None
