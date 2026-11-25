# -*- coding: utf-8 -*-
import base64, json, re, time, random, urllib.request
from urllib.parse import urlencode, quote

try:
    from Crypto.Cipher import AES as _GH_AES
except Exception:
    _GH_AES = None

# 共和动漫搜索（嵌进豆瓣搜索：只加搜索、详情、播放三处，不动豆瓣原有线路）
# 接口：http://bkbfdm.cenmo.fun（HTTPS 会 503，必须走 HTTP）
# ============================================================================
GH_HOST = "http://bkbfdm.cenmo.fun"
GH_PLAY_HOST = "http://jxbfdm.cenmo.fun"
GH_APP_ID = "4150439554430627"
GH_X_VERSION = "2024-09-24"
GH_AUTH_KEY = "ziISjqkXPsGUMRNGyWigxDGtJbfTdcGv"
GH_AUTH_IV = "WonrnVkxeIxDcFbv"
GH_MD5_KEY = "UY9kxQEtk8Dn08Kr"
GH_MD5_IV = "J5jQnzGVRfCe4CUk"
GH_PLAY_AUTH_KEY = "EV330AVbUcpZz5csLp6k8g4XYAqlbWG"
GH_PLAY_HEADER_KEY = "T8qW2mN6rY4pLc9V"
GH_PLAY_EXTRA_KEY = "C6rX9mQ2tV7pLs4N"
GH_PLAY_CHECK_KEY = "522828731F1A016B"
GH_PLAY_PROBE_KEY = "522828731F1A016B"
GH_PLAY_EXPIRE = 600
GH_UA = "Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36"
GH_RSA_N = 23946753643437448996239823079969962944683996343309754151031598024028071884582070922167274523288816507155697876106753330517537469299247060316572098110251505230839642583608034451723983404983162880997911062605335008489522843673495320704289842688269691872439630786262021283379251467376680768247147703137642211573867021069692010451930701239927939984808713325181463940245689161876022507371372197144447121461614205340636499035121331005293806122747516682822560479551102413146820511650377066453956547641984506110102230164302842790073142505167663391732514810976183581811882575525160960155069812595619444819771013889788854040861
GH_RSA_D = 2234012111875376705723641276087345368933548280253838852547525677386936104831389621406697231112010377721744004371831024654534447522706204537521122539116494544781628313108313206857812144865756105015811346823458782701450213867277269188184202789204279965639194693489265577102716686322856191419550193890222995888745534830517935243287912812370674752317461908971028126474909813456167912880515956561543352309076004090053778499458243490091574892210160321852468705333829388604736979368363080648275356771074225774747675890997773882200127065838815470362846759978034199728427869061185087691563416409829670545155074647865527681657
GH_RSA_BYTES = 256

try:
    from Crypto.Cipher import AES as _GH_AES
except Exception:
    _GH_AES = None


def _gh_b64e(obj):
    return base64.urlsafe_b64encode(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).decode("ascii").rstrip("=")


def _gh_b64d(txt):
    txt = str(txt or "")
    txt += "=" * (-len(txt) % 4)
    return json.loads(base64.urlsafe_b64decode(txt.encode("ascii")).decode("utf-8"))


def _gh_md5(s):
    return hashlib.md5(str(s).encode("utf-8")).hexdigest()


def _aes_cbc_encrypt(key, iv, data):
    from Crypto.Cipher import AES
    return AES.new(key, AES.MODE_CBC, iv).encrypt(data)


def _aes_cbc_decrypt(key, iv, data):
    from Crypto.Cipher import AES
    return AES.new(key, AES.MODE_CBC, iv).decrypt(data)


def _gh_pad(data):
    n = 16 - len(data) % 16
    return data + bytes([n]) * n


def _gh_aes_enc(raw, key, iv):
    # 复用豆瓣已有的 AES（有 Crypto 用 Crypto，没有就走纯 Python，256 位也支持）
    return _aes_cbc_encrypt(key, iv, _gh_pad(raw))


def _gh_aes_dec(raw, key, iv):
    plain = _aes_cbc_decrypt(key, iv, raw)
    n = plain[-1] if plain else 0
    if 1 <= n <= 16 and plain[-n:] == bytes([n]) * n:
        plain = plain[:-n]
    return plain


def _gh_rsa_dec(cipher_bytes):
    c = int.from_bytes(cipher_bytes, "big")
    m = pow(c, GH_RSA_D, GH_RSA_N)
    raw = m.to_bytes(GH_RSA_BYTES, "big")
    idx = raw.find(b"\x00", 2)
    if idx < 0:
        idx = 2
    return raw[idx + 1:]


def _gh_auth_header(ts):
    plain = "0.1.0-%s-3-1.0.0-win32" % ts
    inner = base64.b64encode(plain.encode()).decode()
    ct = _gh_aes_enc(inner.encode(), GH_AUTH_KEY.encode(), GH_AUTH_IV.encode())
    return base64.b64encode(ct).decode()


def _gh_http(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "ignore")


def _gh_api(path, params=None):
    ts = str(int(time.time() * 1000))
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-version": GH_X_VERSION,
        "appid": GH_APP_ID,
        "system": "3",
        "requrl": GH_HOST,
        "ts": ts,
        "authentication": _gh_auth_header(ts),
        "User-Agent": GH_UA,
    }
    qs = urlencode(params or {})
    url = GH_HOST + path + (("?" + qs) if qs else "")
    try:
        text = _gh_http(url, headers)
    except Exception:
        return {}
    text = (text or "").strip()
    if not text:
        return {}
    if text[0] == "{":
        try:
            obj = json.loads(text)
        except Exception:
            return {}
    elif "." in text:
        p = text.index(".")
        try:
            aes_key = _gh_rsa_dec(base64.b64decode(text[:p]))
            body = base64.b64decode(text[p + 1:])
            plain = _gh_aes_dec(body, aes_key, aes_key[::-1])
            obj = json.loads(plain.decode("utf-8", "ignore").strip())
        except Exception:
            return {}
    else:
        return {}
    if isinstance(obj, dict) and obj.get("code") == 20000:
        return obj.get("data", obj)
    return obj if isinstance(obj, (dict, list)) else {}


def _gh_clean(s):
    return re.sub(r"[$#]", " ", str(s or "")).strip()


def _gh_search(key, page=1):
    key = str(key or "").strip()
    if not key:
        return []
    data = _gh_api("/pc/video/search", {"key": key, "page": str(page), "limit": "24"})
    items = data.get("items") if isinstance(data, dict) else []
    out = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        vid = str(it.get("id", "") or "").strip()
        name = _gh_clean(it.get("name"))
        if not vid or not name:
            continue
        _k = re.sub(r"[\s·:：\-—_、,，.。!！?？《》<>\[\]()（）]+", "", str(key)).lower()
        _n = re.sub(r"[\s·:：\-—_、,，.。!！?？《》<>\[\]()（）]+", "", name).lower()
        if _k and _n and not (_k in _n or _n in _k):
            continue
        out.append({
            "vod_id": "gh:" + vid,
            "vod_name": name,
            "vod_pic": it.get("pic") or "",
            "vod_remarks": ("共和动漫 · " + _gh_clean(it.get("continu"))) if _gh_clean(it.get("continu")) else "共和动漫",
            "vod_year": str(it.get("year") or ""),
            "type_name": "动漫",
        })
    return out


def _gh_detail(vid):
    vid = str(vid or "").strip()
    if not vid:
        return {}
    data = _gh_api("/pc/video/detail", {"id": vid})
    if not isinstance(data, dict) or not data:
        return {}
    vod = {
        "vod_id": "gh:" + vid,
        "vod_name": _gh_clean(data.get("name")),
        "vod_pic": data.get("pic") or "",
        "vod_year": str(data.get("year") or ""),
        "vod_area": str(data.get("area") or ""),
        "vod_actor": _gh_clean(data.get("actor")),
        "vod_director": _gh_clean(data.get("director")),
        "vod_content": _gh_clean(data.get("content")),
        "vod_remarks": _gh_clean(data.get("continu")),
        "type_name": "动漫",
    }
    froms, urls = [], []
    for part in data.get("parts") or []:
        if not isinstance(part, dict):
            continue
        play = part.get("play") or ""
        eps = part.get("part") or []
        if not play or not eps:
            continue
        label = _gh_clean(part.get("play_zh") or play) or "共和动漫"
        items = []
        for ep in eps:
            ep = str(ep).strip()
            if not ep:
                continue
            token = "gh:" + _gh_b64e({"id": vid, "play": play, "part": ep, "name": vod["vod_name"]})
            items.append("%s$%s" % (_gh_clean(ep), token))
        if items:
            froms.append(label)
            urls.append("#".join(items))
    vod["vod_play_from"] = "$$$".join(froms)
    vod["vod_play_url"] = "$$$".join(urls)
    return vod


def _gh_encrypt_md5_id(md5_id):
    prefix = "%04d" % random.randint(0, 9999)
    scrambled = md5_id.lower()[::-1]
    guard = _gh_md5("%s:%s:%s:%s" % (prefix, scrambled, GH_MD5_KEY, GH_MD5_IV))[:2]
    wrapped = scrambled[:16] + guard + scrambled[16:]
    plain = prefix + "-" + wrapped
    ct = _gh_aes_enc(plain.encode(), GH_MD5_KEY.encode(), GH_MD5_IV.encode())
    return base64.b64encode(ct).decode()


def _gh_gen_auth_param(path, expire, key):
    now = int(time.time())
    exp = now + expire
    rnd = "".join(random.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(16))
    sign = _gh_md5("%s-%d-%s-0-%s" % (path, exp, rnd, key))
    return "sign=%d-%s-0-%s" % (exp, rnd, sign)


def _gh_client_header(path, md5_param, auth_param, key, binds=None, expire=None):
    nonce = "".join(random.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(20))
    seed = [path, md5_param, auth_param]
    exp = None
    if expire:
        exp = int(time.time()) + expire
        seed.append(str(exp))
    seed += (binds or [])
    seed.append(nonce)
    seed.append(key)
    h = _gh_md5("|".join(seed))
    if exp:
        return "v1:%d:%s:%s" % (exp, nonce, h)
    return "v1:%s:%s" % (nonce, h)


def _gh_decrypt_url_field(value):
    if not value:
        return ""
    try:
        raw = base64.b64decode(value)
        return _gh_aes_dec(raw, GH_MD5_IV.encode(), GH_MD5_KEY.encode()).decode("utf-8", "ignore")
    except Exception:
        return ""


def _gh_rewrite_url(url):
    url = str(url or "")
    url = url.replace("play.ddmm.hzhcbkj.cn", "m3bkbfdm.hzhcbkj.cn")
    url = url.replace("new.ddmm.hzhcbkj.cn", "m3bkbfdm.hzhcbkj.cn")
    url = url.replace("bdmov.a.yximgs.com", "v4-kling.kechuangai.com")
    if "hwmov6.a.yximgs.com" in url:
        url = url.replace("hwmov6.a.yximgs.com", "v4-kling.kechuangai.com")
    if re.search(r"v[123]-ad\.video\.yximgs\.com", url):
        url = re.sub(r"v[123]-ad\.video\.yximgs\.com",
                     random.choice(["v1-ad.video.yximgs.com", "alimov2.a.yximgs.com",
                                    "v4-kling.kechuangai.com", "h2.static.yximgs.com"]), url)
    if "sns-video-default.xhscdn.com" in url:
        url = url.replace("sns-video-default.xhscdn.com",
                          random.choice(["sns-video-bd.xhscdn.com", "sns-video-hw.xhscdn.com",
                                         "sns-video-hs.xhscdn.com"]))
    return url


def _gh_resolve_wrap(source):
    md5_id = source[4:] if source.startswith("new-") else source
    if not re.match(r"^[a-fA-F0-9]{32}$", md5_id):
        return []
    md5_param = _gh_encrypt_md5_id(md5_id)
    path = "/"
    auth_param = _gh_gen_auth_param(path, GH_PLAY_EXPIRE, GH_PLAY_AUTH_KEY)
    h_auth = _gh_client_header(path, md5_param, auth_param, GH_PLAY_HEADER_KEY, [], GH_PLAY_EXPIRE)
    h_proof = _gh_client_header(path, md5_param, auth_param, GH_PLAY_EXTRA_KEY, [h_auth])
    h_check = _gh_client_header(path, md5_param, auth_param, GH_PLAY_CHECK_KEY, [h_auth, h_proof])
    url = GH_PLAY_HOST + "/?md5=" + quote(md5_param, safe="") + "&" + auth_param
    headers = {
        "Accept": "*/*",
        "Connection": "keep-alive",
        "User-Agent": GH_UA,
        "X-Goepp-Client-Auth": h_auth,
        "X-Goepp-Client-Proof": h_proof,
        "X-Goepp-Client-Probe": GH_PLAY_PROBE_KEY,
        "X-Goepp-Client-Check": h_check,
    }
    try:
        obj = json.loads(_gh_http(url, headers))
    except Exception:
        return []
    if obj.get("code") != 0:
        return []
    got = []
    for item in (obj.get("data") or {}).get("playAddr") or []:
        if not isinstance(item, dict):
            continue
        addr = _gh_decrypt_url_field(item.get("addr", ""))
        domain = _gh_decrypt_url_field(item.get("m3u8FileDomain", ""))
        play_url = (domain or "") + (addr or "")
        if not play_url.startswith("http"):
            continue
        if domain and "anixx.r2" in domain:
            play_url = "https://sns-music.xhscdn.com/104002e031m0qe7o84s0m6saf3o"
        else:
            play_url = _gh_rewrite_url(play_url)
        got.append((_gh_clean(item.get("desc") or item.get("title") or "") or "默认", play_url))
    return got


def _gh_play(value):
    token = str(value or "")
    if token.startswith("gh:"):
        token = token[3:]
    try:
        payload = _gh_b64d(token)
    except Exception:
        return {"parse": 0, "jx": 0, "url": ""}
    data = _gh_api("/pc/video/play", {
        "id": str(payload.get("id", "")),
        "play": str(payload.get("play", "")),
        "part": str(payload.get("part", "")),
    })
    items = data.get("list") if isinstance(data, dict) else data
    if not isinstance(items, list):
        items = []
    names, urls = [], []
    for it in items:
        if not isinstance(it, dict):
            continue
        name = _gh_clean(it.get("res") or "")
        source = str(it.get("url") or "").strip()
        if not source:
            continue
        if source.startswith("http"):
            names.append(name or "默认")
            urls.append(source)
        elif "wrap_md5_id" in str(it.get("parse") or "") or source.startswith("new-"):
            for nm, u in _gh_resolve_wrap(source):
                names.append(_gh_clean((name + " " + nm).strip()) or "默认")
                urls.append(u)
    if not urls:
        return {"parse": 0, "jx": 0, "url": "", "msg": "共和这条线路没出流，换一条试试"}
    if len(urls) == 1:
        return {"parse": 0, "jx": 0, "url": urls[0], "header": {"User-Agent": GH_UA}}
    mixed = []
    for i in range(len(urls)):
        mixed.append(names[i] or ("线路%d" % (i + 1)))
        mixed.append(urls[i])
    return {"parse": 0, "jx": 0, "url": mixed, "header": {"User-Agent": GH_UA}}




try:
    from base.spider import Spider as BaseSpider
except Exception:
    BaseSpider = object


class Spider(BaseSpider):
    def init(self, cfg):
        return None

    def getName(self):
        return "共和动漫"

    def homeContent(self, filter):
        return {"class": [{"type_id": "1", "type_name": "动漫"}]}

    def homeVideoContent(self):
        return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        try:
            return {"list": _gh_search(key, int(pg or 1))}
        except Exception:
            return {"list": []}

    def detailContent(self, ids):
        vid = str(ids[0] or "")
        if vid.startswith("gh:"):
            vid = vid[3:]
        try:
            v = _gh_detail(vid)
        except Exception:
            v = {}
        return {"list": [v]} if v else {"list": []}

    def playerContent(self, flag, id, vipFlags):
        try:
            return _gh_play(id)
        except Exception as e:
            return {"parse": 0, "jx": 0, "url": "", "msg": str(e)}
