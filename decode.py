#!/usr/bin/env python3
"""TVBox 接口配置解码器：把 raw/*.bin 解码成标准 JSON。

支持格式：
  1. 纯 JSON（可带 BOM、// 整行注释、未转义控制字符）
  2. 图片尾部 base64（PNG IEND 后 / JPEG FFD9 后 / GIF 尾部），可带 `PREFIX**` 前缀
  3. 整文件 base64（可套 gzip）
  4. TVBox 加密 hex：hex("$#key#$") + AES-CBC 密文 hex + hex(iv)
     key/IV 为 ASCII 字符串补 '0' 到 16 字节，AES-CBC + PKCS7
  5. gzip 压缩 JSON

用法：python3 decode.py [raw_dir] [out_dir]
输出：out_dir/<name>.json（解码后的配置），并打印汇总表。
多仓订阅（顶层 urls、无 sites）原样保存，标记为 multi。
"""
import base64
import binascii
import gzip
import json
import os
import re
import sys

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    HAVE_CRYPTO = True
except ImportError:
    HAVE_CRYPTO = False


def _strip_comments(t):
    """去掉 // 整行注释与 ## 整行注释（部分源文件混入 markdown 分隔行）。"""
    return '\n'.join(ln for ln in t.splitlines()
                     if not ln.strip().startswith('//')
                     and not ln.strip().startswith('##'))


def _loads_variants(t):
    """对同一文本尝试多种宽容解析，返回第一个成功的对象。"""
    candidates = [t]
    # 去掉整行 // 注释与 ## 注释
    stripped = _strip_comments(t)
    if stripped != t:
        candidates.append(stripped)
    # 修复形如 "searchable": 0"} 的多余引号（源文件手误）
    fixed = re.sub(r'":\s*(\d)"\}', r'": \1}', t)
    if fixed != t:
        candidates.append(fixed)
        candidates.append(_strip_comments(fixed))
    # 修复未加引号的 name 值： "name": 酷喵🐱橘汁（备用）,
    fixed2 = re.sub(r'"name":\s*([^"\s{][^,\n]*),', r'"name": "\1",', t)
    if fixed2 != t:
        candidates.append(fixed2)
        candidates.append(_strip_comments(fixed2))
    # 修复未加引号的 key： {副标题": -> {"副标题":
    fixed3 = re.sub(r'([{,]\s*)([\u4e00-\u9fffA-Za-z0-9_]+)\s*:', r'\1"\2":', t)
    fixed3b = re.sub(r'([{,]\s*)([\u4e00-\u9fffA-Za-z0-9_]+)":', r'\1"\2":', t)
    if fixed3 != t:
        candidates.append(fixed3)
        candidates.append(_strip_comments(fixed3))
    if fixed3b != t:
        candidates.append(fixed3b)
        candidates.append(_strip_comments(fixed3b))
    # 修复尾随逗号： ,} 或 ,] -> } 或 ]（源文件手误）
    fixed4 = re.sub(r',(\s*[}\]])', r'\1', t)
    if fixed4 != t:
        candidates.append(fixed4)
        candidates.append(_strip_comments(fixed4))
        # 组合：尾随逗号 + 未引 key
        fixed5 = re.sub(r'([{,]\s*)([\u4e00-\u9fffA-Za-z0-9_]+)":', r'\1"\2":', fixed4)
        if fixed5 != fixed4:
            candidates.append(fixed5)
            candidates.append(_strip_comments(fixed5))
    for c in candidates:
        for strict in (True, False):
            try:
                obj = json.loads(c, strict=strict)
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass
        # 允许尾部多余内容（如 HTML 尾巴）：只解析第一个 JSON 值
        try:
            obj, _ = json.JSONDecoder(strict=False).raw_decode(c)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    return None


def try_json(text):
    """尝试解析 JSON，容忍 BOM、// 注释行、控制字符、尾部垃圾。"""
    if text is None:
        return None
    t = text.strip()
    if t.startswith('\ufeff'):
        t = t[1:]
    obj = _loads_variants(t)
    if obj is not None:
        return obj
    # 去掉控制字符（保留 \n \t \r）再试
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', t)
    return _loads_variants(cleaned)


def b64_json(s):
    """base64 文本 -> JSON。处理 `PREFIX**payload` 形式。"""
    if not s:
        return None
    s = s.strip()
    if '**' in s:
        s = s.split('**', 1)[1]
    s = re.sub(r'\s+', '', s)
    if len(s) < 20:
        return None
    # 补齐 padding
    s += '=' * (-len(s) % 4)
    try:
        raw = base64.b64decode(s, validate=False)
    except (binascii.Error, ValueError):
        return None
    # 可能套 gzip
    try:
        raw = gzip.decompress(raw)
    except Exception:
        pass
    for enc in ('utf-8', 'gbk', 'latin-1'):
        try:
            return try_json(raw.decode(enc))
        except UnicodeDecodeError:
            continue
    return None


def tvbox_decrypt(hexstr):
    """TVBox hex 加密格式解密。"""
    if not HAVE_CRYPTO:
        return None, 'pycryptodome 未安装'
    hexstr = hexstr.strip()
    if not re.fullmatch(r'[0-9a-fA-F]+', hexstr):
        return None, '不是纯 hex'
    # 头部标记 hex("#$") = 2324
    marker = '#$'.encode().hex()  # '2324'
    pos = hexstr.find(marker)
    if pos == -1:
        return None, '无 #$ 头部标记'
    header_end = pos + 4
    header_hex = hexstr[:header_end]
    iv_hex = hexstr[-26:]
    cipher_hex = hexstr[header_end:-26]
    try:
        real_key = bytes.fromhex(header_hex).decode()[2:-2]
        real_iv = bytes.fromhex(iv_hex).decode()
    except Exception as e:
        return None, f'key/iv 解析失败: {e}'
    try:
        key = real_key.ljust(16, '0').encode()
        iv = real_iv.ljust(16, '0').encode()
        cipher = AES.new(key, AES.MODE_CBC, iv)
        dec = unpad(cipher.decrypt(bytes.fromhex(cipher_hex)), 16)
        obj = try_json(dec.decode('utf-8'))
        if obj is None:
            return None, '解密后不是 JSON'
        return obj, 'tvbox-hex'
    except Exception as e:
        return None, f'AES 解密失败: {e}'


def decode_bytes(data):
    """返回 (obj, format_desc)；obj 为 None 时 format_desc 是失败原因。"""
    # 1. gzip 整体
    try:
        dec = gzip.decompress(data)
        obj = try_json(dec.decode('utf-8', errors='ignore'))
        if obj is not None:
            return obj, 'gzip+json'
    except Exception:
        pass

    # 2. 直接 JSON
    for enc in ('utf-8', 'gbk'):
        try:
            obj = try_json(data.decode(enc))
            if obj is not None:
                return obj, 'json'
        except UnicodeDecodeError:
            continue

    # 3. 图片尾部 base64
    tail = None
    if data.startswith(b'\x89PNG'):
        i = data.find(b'IEND')
        if i != -1:
            tail = data[i + 8:]
    elif data.startswith(b'\xff\xd8'):
        i = data.rfind(b'\xff\xd9')
        if i != -1:
            tail = data[i + 2:]
    elif data.startswith(b'GIF8'):
        # GIF 尾部：找最后一个 0x3B 之后的长 base64 段；退化为全文搜索
        tail = data
    if tail:
        try:
            t = tail.decode('latin-1')
            obj = b64_json(t)
            if obj is not None:
                return obj, 'image-tail-b64'
        except Exception:
            pass
        # 全文搜索长 base64 段
        try:
            text = data.decode('latin-1')
            for m in re.finditer(r'[A-Za-z0-9+/=_-]{200,}', text):
                obj = b64_json(m.group(0))
                if obj is not None:
                    return obj, 'image-embedded-b64'
        except Exception:
            pass

    # 4. 整文件 base64
    try:
        t = data.decode('ascii')
        obj = b64_json(t)
        if obj is not None:
            return obj, 'whole-b64'
    except Exception:
        pass

    # 5. TVBox hex 加密
    try:
        t = data.decode('ascii').strip()
        # 去掉 // 注释行
        t = '\n'.join(ln for ln in t.splitlines() if not ln.strip().startswith('//')).strip()
        if re.fullmatch(r'[0-9a-fA-F]+', t):
            obj, why = tvbox_decrypt(t)
            if obj is not None:
                return obj, 'tvbox-hex'
            return None, f'hex 加密但解密失败：{why}'
    except Exception:
        pass

    return None, '未知格式（非 JSON/图片/base64/hex 加密）'


def main():
    raw_dir = sys.argv[1] if len(sys.argv) > 1 else 'raw'
    out_dir = sys.argv[2] if len(sys.argv) > 2 else 'decoded'
    os.makedirs(out_dir, exist_ok=True)
    print(f"{'文件':<16} {'格式':<20} {'站点':>5} {'lives':>5} {'parses':>6}  spider")
    print('-' * 100)
    results = {}
    for fn in sorted(os.listdir(raw_dir)):
        if not fn.endswith('.bin'):
            continue
        name = fn[:-4]
        path = os.path.join(raw_dir, fn)
        data = open(path, 'rb').read()
        if len(data) == 0:
            print(f"{name:<16} {'空文件':<20}")
            results[name] = {'ok': False, 'error': '空文件（拉取失败）'}
            continue
        obj, fmt = decode_bytes(data)
        if obj is None:
            print(f"{name:<16} {'失败: ' + fmt:<20}")
            results[name] = {'ok': False, 'error': fmt}
            # 清理旧的解码残留，避免失败文件留下脏输出
            stale = os.path.join(out_dir, name + '.json')
            if os.path.exists(stale):
                os.remove(stale)
            continue
        sites = obj.get('sites', []) if isinstance(obj, dict) else []
        lives = obj.get('lives', []) if isinstance(obj, dict) else []
        parses = obj.get('parses', []) if isinstance(obj, dict) else []
        urls = obj.get('urls', []) if isinstance(obj, dict) else []
        spider = (obj.get('spider', '') or '') if isinstance(obj, dict) else ''
        kind = 'multi' if urls and not sites else 'single'
        with open(os.path.join(out_dir, name + '.json'), 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        spider_short = spider[:60]
        print(f"{name:<16} {fmt + '/' + kind:<20} {len(sites):>5} {len(lives):>5} {len(parses):>6}  {spider_short}")
        results[name] = {'ok': True, 'format': fmt, 'kind': kind,
                         'sites': len(sites), 'lives': len(lives),
                         'parses': len(parses), 'urls': len(urls),
                         'spider': spider}
    with open(os.path.join(out_dir, '_summary.json'), 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    ok = sum(1 for r in results.values() if r.get('ok'))
    print('-' * 100)
    print(f"解码成功 {ok}/{len(results)}")


if __name__ == '__main__':
    main()
