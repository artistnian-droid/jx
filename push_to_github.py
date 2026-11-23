#!/usr/bin/env python3
"""把 tv 的文件批量推到 GitHub 仓库（一次原子提交）。

用法：python3 push_to_github.py
只推流水线需要的文件 + 缓存 + 文档，不推中间工作文件（raw/、fetch 脚本等）。
凭证走 custom.github 连接的 surrogate 交换，绝不出现在本文件里。
"""
import base64
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
sys.path.insert(0, os.path.expanduser("~/workspace/custom-connectors/custom.github/bin"))
from dynamic_credentials import add_surrogate_to_request, read_json_response
import urllib.request
import urllib.error

API = "https://api.github.com"
OWNER = "artistnian-droid"
REPO = "jx"
BRANCH = "main"
WORKDIR = os.path.dirname(os.path.abspath(__file__))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeError("redirect refused")


def call(method, path, body=None):
    url = API + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    add_surrogate_to_request(req, "custom.github", allowed_hosts=["api.github.com"])
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=120) as resp:
            return resp.status, read_json_response(resp)
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode("utf-8", "replace"))
        except Exception:
            detail = {"message": f"HTTP {e.code}"}
        return e.code, detail


def collect_files():
    """返回 [(repo_path, local_path)]。"""
    files = []
    for name in ["merge.py", "decode.py", "sources.json", "urlmap.json",
                 "merged.json", "merge_stats.json", "REPORT.md", "README.md"]:
        files.append((name, os.path.join(WORKDIR, name)))
    files.append((".github/workflows/daily-refresh.yml",
                  os.path.join(WORKDIR, ".github/workflows/daily-refresh.yml")))
    dec = os.path.join(WORKDIR, "decoded")
    for fn in sorted(os.listdir(dec)):
        if fn.endswith(".json"):
            files.append((f"decoded/{fn}", os.path.join(dec, fn)))
    return files


def create_blob(item):
    repo_path, local_path = item
    with open(local_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("ascii")
    status, res = call("POST", f"/repos/{OWNER}/{REPO}/git/blobs",
                       {"content": content, "encoding": "base64"})
    if status != 201:
        raise RuntimeError(f"blob 失败 {repo_path}: HTTP {status} {res}")
    return repo_path, res["sha"]


def main():
    files = collect_files()
    print(f"共 {len(files)} 个文件待推送")

    status, ref = call("GET", f"/repos/{OWNER}/{REPO}/git/ref/heads/{BRANCH}")
    assert status == 200, f"读分支失败: {ref}"
    head_sha = ref["object"]["sha"]
    status, head_commit = call("GET", f"/repos/{OWNER}/{REPO}/git/commits/{head_sha}")
    assert status == 200, f"读 HEAD 提交失败: {head_commit}"
    base_tree = head_commit["tree"]["sha"]
    print(f"HEAD: {head_sha[:8]}  base_tree: {base_tree[:8]}")

    blobs = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(create_blob, it): it[0] for it in files}
        for fut in as_completed(futs):
            repo_path, sha = fut.result()
            blobs[repo_path] = sha
    print(f"blobs 建好: {len(blobs)}")

    tree = [{"path": p, "mode": "100644", "type": "blob", "sha": s}
            for p, s in sorted(blobs.items())]
    status, res = call("POST", f"/repos/{OWNER}/{REPO}/git/trees",
                       {"base_tree": base_tree, "tree": tree})
    assert status == 201, f"建 tree 失败: {res}"
    tree_sha = res["sha"]
    print(f"tree: {tree_sha[:8]}")

    msg = "聚合配置首次发布：105 个接口 / 4325 站点 + 每日自动刷新"
    status, res = call("POST", f"/repos/{OWNER}/{REPO}/git/commits",
                       {"message": msg, "tree": tree_sha, "parents": [head_sha]})
    assert status == 201, f"建 commit 失败: {res}"
    commit_sha = res["sha"]
    print(f"commit: {commit_sha[:8]}")

    status, res = call("PATCH", f"/repos/{OWNER}/{REPO}/git/refs/heads/{BRANCH}",
                       {"sha": commit_sha, "force": False})
    assert status == 200, f"更新分支失败: {res}"
    print(f"推送成功：https://github.com/{OWNER}/{REPO} @ {commit_sha[:8]}")


if __name__ == "__main__":
    main()
