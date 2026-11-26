# -*- coding: utf-8 -*-
# 网盘聚合·补封面外壳：原样加载 0优C跨可.py，只在返回结果时补 vod_pic
import re, json, html, urllib.request, urllib.parse

_SRC = "https://ghfast.top/https://raw.githubusercontent.com/gaijinxiang/wmz-five-src/main/src/pan_engine.py"
_NS = {}
_PIC = {}
_HOST = "https://www.xmfyy.com"
_UA = ("Mozilla/5.0 (Linux; Android 11; Mobile) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36")


def _get(url, timeout=5):
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def _clean(s):
    return re.sub(r"<[^>]+>", "", html.unescape(s or "")).strip()


def _tidy(t):
    t = _clean(t)
    t = re.sub(r"（[^）]*）|（[^）]*|\[[^\]]*\]", " ", t)
    t = re.sub(r"【[^】]*】", " ", t)
    t = re.sub(r"\b(4K|8K|1080P|2160P|HDR|高清|蓝光|国语|中字|中文字幕|WEB-DL|HDTV|更新?至?)\b", " ", t, flags=re.I)
    t = re.sub(r"(更|更新|更新至|全)[至新]?\s*[0-9]+\s*集?(完结)?", " ", t)
    t = re.sub(r"[0-9]+\s*集(全|完结)?", " ", t)
    t = re.sub(r"第[一二三四五六七八九十0-9]+季", " ", t)
    t = re.sub(r"[·|/\\:：\-—_]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _db_pic(t):
    """豆瓣 suggest 拿海报：整名 → 去修饰 → 取前 4~6 字，逐级降级"""
    cands = []
    a = _tidy(t)
    if a:
        cands.append(a)
    b = re.split(r"[ (（\[]", t)[0].strip()
    if b and b not in cands:
        cands.append(b)
    for q in cands[:2]:
        for _q in (q, q[:6].strip(), q[:4].strip()):
            if not _q:
                continue
            try:
                raw = _get("https://movie.douban.com/j/subject_suggest?%s" % urllib.parse.urlencode({"q": _q}), timeout=2.5)
                arr = json.loads(raw)
            except Exception:
                continue
            if not isinstance(arr, list) or not arr:
                continue
            for it in arr:
                nm = _clean(it.get("title") or it.get("sub_title") or "")
                img = str(it.get("img") or "").replace("\\/", "/")
                if not img:
                    continue
                if not nm or nm[:3] in t or t[:3] in nm or _q in nm:
                    return img.replace("/s_ratio_poster/", "/l_ratio_poster/")
    return ""


def _pic_of(title):
    t = _clean(title)
    if not t:
        return ""
    if _PIC.get(t):
        return _PIC[t]
    pic = _db_pic(t)
    if not pic:
        try:
            q = _tidy(t) or t
            page = _get("%s/search?%s" % (_HOST, urllib.parse.urlencode({"keyword": q})), timeout=4)
            for m in re.finditer(r'href="/detail/(\d+)\.html"', page):
                chunk = page[m.start():m.start() + 1800]
                pm = re.search(r'<img[^>]+(?:data-src|src)="(https?://[^"]+)"', chunk)
                if pm:
                    pic = pm.group(1)
                    break
        except Exception:
            pic = ""
    if pic:
        _PIC[t] = pic
    return pic


def _drop(items):
    """过滤卡卡 / 123 网盘的结果"""
    try:
        def _bad(x):
            src = str(x.get("vod_id", "")).split("@")[0]
            nm = str(x.get("vod_name", ""))
            if "卡卡" in src or "卡卡" in nm:
                return True
            if re.match(r"^123(网盘|云盘|pan)?", src, re.I):
                return True
            if re.search(r"123\s*(网盘|云盘)", nm):
                return True
            return False
        items[:] = [x for x in items if not _bad(x)]
    except Exception:
        pass
    return items



_GLM_KEY = ""
_NAME_CACHE = {}


def _tidy_name(t):
    t = _clean(t)
    t = re.sub(r"[【\[][^】\]]*[】\]]", " ", t)
    t = re.sub(r"（[^）]*）|\([^)]*\)", " ", t)
    t = re.sub(r"\b(4K|8K|1080P|2160P|HDR|高清|蓝光|国语|中字|中文字幕|WEB-DL|HDTV|NF|内封|简中|更至|更新至)\b", " ", t, flags=re.I)
    t = re.sub(r"(更|更新|更新至|全|更至)\s*(EP|E)?\s*[0-9]+\s*(集|话)?(完结)?", " ", t, flags=re.I)
    t = re.sub(r"0?4K|8K|内封|简中|国语|中字|高码率|高码|臻彩|蓝光|HDR", " ", t, flags=re.I)
    t = re.sub(r"[0-9]+\s*集(全|完结)?", " ", t)
    t = re.sub(r"第[一二三四五六七八九十0-9]+季", " ", t)
    t = re.sub(r"[·|/\\:：\-—_]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _name_ok(key, name):
    k = _tidy_name(key)
    n = _tidy_name(name)
    if not k or not n:
        return True
    k2 = re.sub(r"\s+", "", k)
    n2 = re.sub(r"\s+", "", n)
    if k2 in n2 or n2 in k2:
        return True
    # 去掉季数/第二部分再比
    k3 = re.sub(r"第[一二三四五六七八九十0-9]+季|第[一二三四五六七八九十0-9]+部", "", k2)
    n3 = re.sub(r"第[一二三四五六七八九十0-9]+季|第[一二三四五六七八九十0-9]+部", "", n2)
    if len(k3) >= 2 and k3 in n3:
        return True
    # 都取前两个字判断（防"两京十五日"对"两京十五日(臻彩)"这类）
    return bool(k3[:2] and k3[:2] in n3 and len(k3) >= 3)


def _fill(items):
    try:
        import concurrent.futures as _cf
        need = [x for x in items if not str(x.get("vod_pic") or "").strip()]
        need = need[:14]
        if not need:
            return
        with _cf.ThreadPoolExecutor(max_workers=14) as ex:
            fut = {ex.submit(_pic_of, x.get("vod_name")): x for x in need}
            for f in _cf.as_completed(fut, timeout=5):
                v = fut[f]
                try:
                    p = f.result()
                except Exception:
                    p = ""
                if p:
                    v["vod_pic"] = p
    except Exception:
        pass


def _load():
    if _NS.get("Spider"):
        return _NS["Spider"]
    req = urllib.request.Request(_SRC, headers={"User-Agent": "okhttp/3.12.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        txt = r.read().decode("utf-8", "ignore")
    ns = {"__name__": "pan_agg_remote", "__file__": __file__}
    exec(compile(txt, "pan_agg_remote.py", "exec"), ns)
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
        self._impl().init(extend)

    def homeContent(self, filter):
        r = self._impl().homeContent(filter)
        _fill((r or {}).get("list") or [])
        return r

    def homeVideoContent(self):
        r = self._impl().homeVideoContent()
        _drop((r or {}).get("list") or [])
        _fill((r or {}).get("list") or [])
        return r

    def categoryContent(self, tid, pg, filter, extend):
        r = self._impl().categoryContent(tid, pg, filter, extend)
        _drop((r or {}).get("list") or [])
        _fill((r or {}).get("list") or [])
        return r

    def searchContent(self, key, quick, pg="1"):
        r = self._impl().searchContent(key, quick, pg)
        items = (r or {}).get("list") or []
        _drop(items)
        try:
            items[:] = [x for x in items if _name_ok(key, x.get("vod_name"))]
        except Exception:
            pass
        for x in items:
            try:
                nm = _tidy_name(x.get("vod_name"))
                if nm and len(nm) <= len(_clean(x.get("vod_name"))):
                    x["vod_name"] = nm
            except Exception:
                pass
        _fill(items)
        return r

    def detailContent(self, ids):
        r = self._impl().detailContent(ids)
        try:
            for v in (r or {}).get("list") or []:
                if not str(v.get("vod_pic") or "").strip():
                    p = _pic_of(v.get("vod_name"))
                    if p:
                        v["vod_pic"] = p
        except Exception:
            pass
        return r

    def playerContent(self, flag, pid, vipFlags):
        return self._impl().playerContent(flag, pid, vipFlags)

    def localProxy(self, param):
        try:
            return self._impl().localProxy(param)
        except Exception:
            return [404, "text/plain", b"not found", {}]

    def action(self, action):
        return None
