#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘基地（guangsuys.top）—— 搜索 + 网盘线路源
--------------------------------------------------
搜索：/api/other/web_search?title=xx  （SSE 流，每行 data: {json}）
解密：POST /api/other/save_url {url: encodeURIComponent(加密串), title}
      → 返回真实分享链（quark / uc / baidu / xunlei）

线路：
  夸克 / UC —— 免登可列文件（已验证 0.4s / 1.2s），播放需网盘登录（取直链会校验 auth）
  百度 / 迅雷 —— 只给分享链，需自行转存

ext：
{
  "quark_cookie": "……",      # 夸克网盘登录 cookie，取直链+转存必需
  "uc_cookie": "……",         # UC 网盘 cookie（可选，不填则 UC 线只列不播）
  "max_files": 60             # 每个分享最多列多少集
}
"""
import base64
import json
import re
import time
import requests
from urllib.parse import quote

HOST = "https://guangsuys.top"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) quark-cloud-drive/2.5.20 Chrome/100.0.4896.160 "
      "Electron/18.3.5.4-b478491 Safari/537.36")
UC_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) uc-cloud-drive/2.5.20 Chrome/100.0.4896.160 "
         "Electron/18.3.5.4-b478491 Safari/537.36")

TYPES = {"quark": "夸克", "uc": "UC", "baidu": "百度", "xunlei": "迅雷"}
PAN_RANK = ["quark", "uc", "baidu", "xunlei"]

_CACHE = {}          # title -> (ts, items)
_CACHE_TTL = 600


# ---------------------------------------------------------------------------
# 盘基地接口
# ---------------------------------------------------------------------------
def pj_search(kw):
    ts, hit = _CACHE.get(kw, (0, None))
    if hit and time.time() - ts < _CACHE_TTL:
        return hit
    items = []
    try:
        r = requests.get(f"{HOST}/api/other/web_search?title={quote(kw)}",
                         headers={"User-Agent": UA, "Referer": HOST + "/"},
                         timeout=40)
        r.encoding = "utf-8"
        for line in r.text.split("\n"):
            s = line[5:].strip() if line.startswith("data:") else ""
            if not s.startswith("{"):
                continue
            try:
                o = json.loads(s)
            except Exception:
                continue
            if o.get("title") and o.get("url") and o.get("is_type"):
                items.append(o)
    except Exception:
        pass
    _CACHE[kw] = (time.time(), items)
    return items


def pj_decrypt(enc, title=""):
    try:
        r = requests.post(f"{HOST}/api/other/save_url",
                          json={"url": quote(enc), "title": title},
                          headers={"User-Agent": UA, "Referer": HOST + "/"},
                          timeout=25)
        d = (r.json() or {}).get("data") or {}
        return d.get("url", "") or ""
    except Exception:
        return ""


def _b64(s):
    return base64.urlsafe_b64encode(s.encode("utf-8")).decode().rstrip("=")


def _unb64(s):
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s.encode()).decode("utf-8", "ignore")


# ---------------------------------------------------------------------------
# 夸克：免登列目录 / 登录后转存取直链
# ---------------------------------------------------------------------------
QAPI = "https://drive-pc.quark.cn/1/clouddrive"
QRE = re.compile(r"https?://pan\.quark\.cn/s/([0-9a-zA-Z]+)(?:\?pwd=(\w+))?")


class Quark:
    def __init__(self, cookie=""):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Referer": "https://pan.quark.cn"})
        self.cookie = cookie or ""
        if self.cookie:
            self.s.headers.update({"Cookie": self.cookie})
        self._st = {}

    def stoken(self, pwd_id, pwd=""):
        if pwd_id in self._st:
            return self._st[pwd_id]
        try:
            d = self.s.post(f"{QAPI}/share/sharepage/token?pr=ucpro&fr=pc",
                            json={"pwd_id": pwd_id, "passcode": pwd or ""}, timeout=15).json()
            st = (d.get("data") or {}).get("stoken", "") or ""
        except Exception:
            st = ""
        if st:
            self._st[pwd_id] = st
        return st

    def walk(self, share_url, limit=0):
        m = QRE.search(share_url or "")
        if not m:
            return []
        pwd_id, pwd = m.group(1), m.group(2) or ""
        st = self.stoken(pwd_id, pwd)
        if not st:
            return []
        out = []
        self._walk(pwd_id, st, "0", out, 0, limit)
        return out

    def _walk(self, pwd_id, st, pdir, out, depth, limit=0):
        if depth > 10 or (limit and len(out) >= limit):
            return
        page, size = 1, 50
        while True:
            url = (f"{QAPI}/share/sharepage/detail?pr=ucpro&fr=pc&pwd_id={pwd_id}"
                   f"&stoken={quote(st)}&pdir_fid={pdir}&force=0&_page={page}"
                   f"&_size={size}&_sort=file_type:asc,file_name:asc")
            try:
                d = self.s.get(url, timeout=12).json()
            except Exception:
                break
            lst = (d.get("data") or {}).get("list") or []
            if not lst:
                break
            for it in lst:
                if it.get("dir"):
                    self._walk(pwd_id, st, it.get("fid", "0"), out, depth + 1, limit)
                elif it.get("file") and it.get("category") in (1, 2):
                    out.append({"fid": it.get("fid", ""),
                                "name": it.get("file_name", ""),
                                "size": int(it.get("size") or 0),
                                "tok": it.get("share_fid_token", ""),
                                "pwd_id": pwd_id, "st": st})
                if limit and len(out) >= limit:
                    return
            if len(lst) < size:
                break
            page += 1

    def save_and_link(self, pwd_id, st, fid, tok):
        """转存到自己的空间 → 取下载直链"""
        if not self.cookie:
            return "", "未配置 quark_cookie"
        try:
            sv = self.s.post(f"{QAPI}/share/sharepage/save?pr=ucpro&fr=pc",
                             json={"fid_list": [fid], "fid_token_list": [tok],
                                   "to_pdir_fid": "0", "pwd_id": pwd_id, "stoken": st,
                                   "pdir_fid": "0", "scene": "link"}, timeout=20).json()
            if sv.get("code") != 0:
                return "", sv.get("message", "转存失败")
            tid = (sv.get("data") or {}).get("task_id", "")
        except Exception as e:
            return "", f"转存异常 {type(e).__name__}"
        own = ""
        for i in range(8):
            time.sleep(1)
            try:
                t = self.s.get(f"{QAPI}/task?pr=ucpro&fr=pc&task_id={tid}&retry_index={i}",
                               timeout=15).json()
            except Exception:
                continue
            d = t.get("data") or {}
            if d.get("status") == 2:
                sa = d.get("save_as") or {}
                lids = sa.get("save_as_top_fids") or []
                own = lids[0] if lids else ""
                break
        if not own:
            return "", "转存超时"
        try:
            d = self.s.post(f"{QAPI}/file/download?pr=ucpro&fr=pc",
                            json={"fids": [own]}, timeout=20).json()
            arr = d.get("data") or []
            if arr:
                return arr[0].get("download_url", "") or "", ""
            return "", d.get("message", "取直链失败")
        except Exception as e:
            return "", f"取直链异常 {type(e).__name__}"


# ---------------------------------------------------------------------------
# UC：免登列目录（播放同样需要登录）
# ---------------------------------------------------------------------------
UAPI = "https://pc-api.uc.cn/1/clouddrive"
URE = re.compile(r"https?://drive\.uc\.cn/s/([0-9a-zA-Z]+)(?:\?pwd=(\w+))?")


class UC:
    def __init__(self, cookie=""):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UC_UA, "Referer": "https://drive.uc.cn"})
        self.cookie = cookie or ""
        if self.cookie:
            self.s.headers.update({"Cookie": self.cookie})
        self._st = {}

    def stoken(self, pwd_id, pwd=""):
        if pwd_id in self._st:
            return self._st[pwd_id]
        try:
            d = self.s.post(f"{UAPI}/share/sharepage/token?__t={int(time.time()*1000)}&pr=UCBrowser&fr=pc",
                            json={"pwd_id": pwd_id, "passcode": pwd or ""}, timeout=15).json()
            st = (d.get("data") or {}).get("stoken", "") or ""
        except Exception:
            st = ""
        if st:
            self._st[pwd_id] = st
        return st

    def walk(self, share_url, limit=0):
        m = URE.search(share_url or "")
        if not m:
            return []
        pwd_id, pwd = m.group(1), m.group(2) or ""
        st = self.stoken(pwd_id, pwd)
        if not st:
            return []
        out = []
        self._walk(pwd_id, st, "0", out, 0, limit)
        return out

    def _walk(self, pwd_id, st, pdir, out, depth, limit=0):
        if depth > 10 or (limit and len(out) >= limit):
            return
        page, size = 1, 50
        while True:
            url = (f"{UAPI}/share/sharepage/detail?pr=UCBrowser&fr=pc&pwd_id={pwd_id}"
                   f"&stoken={quote(st)}&pdir_fid={pdir}&force=0&_page={page}"
                   f"&_size={size}&_sort=file_type:asc,file_name:asc")
            try:
                d = self.s.get(url, timeout=12).json()
            except Exception:
                break
            lst = (d.get("data") or {}).get("list") or []
            if not lst:
                break
            for it in lst:
                if it.get("dir"):
                    self._walk(pwd_id, st, it.get("fid", "0"), out, depth + 1, limit)
                elif it.get("file") and it.get("category") in (1, 2):
                    out.append({"fid": it.get("fid", ""),
                                "name": it.get("file_name", ""),
                                "size": int(it.get("size") or 0),
                                "tok": it.get("share_fid_token", ""),
                                "pwd_id": pwd_id, "st": st})
                if limit and len(out) >= limit:
                    return
            if len(lst) < size:
                break
            page += 1


def _fmt(sz):
    try:
        sz = int(sz or 0)
    except Exception:
        return ""
    if sz >= 1073741824:
        return f"{sz/1073741824:.1f}G"
    if sz:
        return f"{sz/1048576:.0f}M"
    return ""


# ---------------------------------------------------------------------------
class Spider:
    def __init__(self):
        self.q = None
        self.u = None
        self.ext = {}

    def init(self, extend=""):
        try:
            e = json.loads(extend) if isinstance(extend, str) and extend.strip() else (extend or {})
        except Exception:
            e = {}
        if not isinstance(e, dict):
            e = {}
        self.ext = e
        self.q = Quark(e.get("quark_cookie", ""))
        self.u = UC(e.get("uc_cookie", ""))
        self.limit = int(e.get("max_files", 60) or 60)

    def homeContent(self, filter):
        cats = [{"type_id": t, "type_name": n} for t, n in TYPES.items()]
        return {"class": cats, "list": []}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        return {"page": int(pg or 1), "pagecount": 1, "limit": 20, "total": 0, "list": []}

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        items = pj_search(key)
        groups, order = {}, []
        for it in items:
            t = it.get("title", "").strip()
            if not t:
                continue
            if t not in groups:
                groups[t] = []
                order.append(t)
            groups[t].append(it)
        out = []
        for t in order[:40]:
            ts = [i["is_type"] for i in groups[t]]
            uniq = [TYPES[x] for x in PAN_RANK if x in ts]
            out.append({"vod_id": _b64(t), "vod_name": t, "vod_pic": "",
                        "vod_remarks": "·".join(uniq) if uniq else "网盘"})
        return {"list": out}

    # ---------------- 详情 ----------------
    def detailContent(self, array):
        if not array:
            return {"list": []}
        vid = array[0]
        title = _unb64(vid) if not vid.startswith("http") else vid
        if title.startswith("http"):
            return {"list": [{"vod_id": vid, "vod_name": title,
                              "vod_play_from": "网盘", "vod_play_url": f"分享${vid}"}]}
        items = pj_search(title)
        sel = []
        for t in PAN_RANK:
            for it in items:
                if it.get("is_type") == t and it.get("title", "").strip() == title.strip():
                    sel.append(it)
                    break
        if not sel:
            for t in PAN_RANK:
                for it in items:
                    if it.get("is_type") == t:
                        sel.append(it)
                        break
        # 只保留能列目录的夸克/UC，并行解密+列目录（目标 6s 内出结果）
        def build(it):
            t = it["is_type"]
            link = pj_decrypt(it["url"], it.get("title", ""))
            if not link:
                return None
            if t == "quark" and self.q:
                eps = self.q.walk(link, limit=self.limit)
                name = "盘基地·夸克"
            elif t == "uc" and self.u:
                eps = self.u.walk(link, limit=self.limit)
                name = "盘基地·UC"
            else:
                return None
            if not eps:
                return None
            parts = [f"{i+1}${e['pwd_id']}|{e['fid']}|{e['tok']}" for i, e in enumerate(eps)]
            return name, "#".join(parts)

        from concurrent.futures import ThreadPoolExecutor
        froms, urls = [], []
        todo = [it for it in sel if it["is_type"] in ("quark", "uc")]
        if todo:
            with ThreadPoolExecutor(max_workers=2) as pool:
                for res in pool.map(build, todo):
                    if res:
                        froms.append(res[0])
                        urls.append(res[1])
        if not froms:
            return {"list": [{"vod_id": vid, "vod_name": title, "vod_pic": "",
                              "vod_play_from": "提示", "vod_play_url": "未取到网盘文件$none"}]}
        return {"list": [{"vod_id": vid, "vod_name": title, "vod_pic": "",
                          "vod_play_from": "$$$".join(froms),
                          "vod_play_url": "$$$".join(urls)}]}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, pid, vipFlags):
        if pid == "none":
            return {"parse": 0, "url": "", "header": ""}
        if pid.startswith("http"):
            return {"parse": 1, "url": pid, "header": ""}
        kind = "夸克" if "夸克" in (flag or "") else ("UC" if "UC" in (flag or "") else "")
        if kind == "夸克":
            try:
                pwd_id, fid, tok = pid.split("|", 2)
            except Exception:
                return {"parse": 0, "url": "", "header": ""}
            st = self.q.stoken(pwd_id)
            url, err = self.q.save_and_link(pwd_id, st, fid, tok)
            if not url:
                return {"parse": 1, "url": "", "header": "", "msg": err}
            h = {"User-Agent": UA, "Cookie": self.q.cookie, "Referer": "https://pan.quark.cn"}
            return {"parse": 0, "url": url, "header": h}
        return {"parse": 1, "url": "", "header": ""}
