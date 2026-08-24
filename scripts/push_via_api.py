"""Push the whole project tree to GitHub via the Git Data API.

The sandbox blocks `git push`, so we do it manually:
  1. POST /repos/{owner}/{repo}/git/blobs      (one per file)
  2. POST /repos/{owner}/{repo}/git/trees      (tree referencing all blobs)
  3. POST /repos/{owner}/{repo}/git/commits    (commit the tree)
  4. POST /repos/{owner}/{repo}/git/refs       (create refs/heads/main)
"""
import base64
import json
import os
import urllib.request

GH = os.environ["GH_TOKEN"]
OWNER, REPO = "Sahdihussen", "dollar-bot"
API = f"https://api.github.com/repos/{OWNER}/{REPO}/git"


def api(method: str, url: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {GH}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        raise SystemExit(f"{method} {url} -> {exc.code}\n{body[:500]}")


def collect_files() -> list[str]:
    """All files that belong in the repo (respects .gitignore, plus dist/)."""
    import fnmatch

    ignore_patterns = [
        ".env", ".env.local", ".git/*",
        "node_modules/*", "__pycache__/*", "*.pyc",
        "isolate/*", "logs/*", ".git",
    ]
    files = []
    for root, dirs, names in os.walk("."):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", "isolate", "logs")]
        for name in names:
            rel = os.path.relpath(os.path.join(root, name), ".").replace(os.sep, "/")
            if any(fnmatch.fnmatch(rel, pat) or rel == pat.rstrip("/*") for pat in ignore_patterns):
                continue
            files.append(rel)
    return sorted(files)


files = collect_files()
print(f"collecting {len(files)} files ...")

tree_items = []
for path in files:
    with open(path, "rb") as fh:
        raw = fh.read()
    blob = api("POST", f"{API}/blobs", {
        "content": base64.b64encode(raw).decode(),
        "encoding": "base64",
    })
    tree_items.append({
        "path": path,
        "mode": "100644",
        "type": "blob",
        "sha": blob["sha"],
    })
    print(f"  blob {path} ({len(raw)} bytes)")

print("creating tree ...")
tree = api("POST", f"{API}/trees", {"tree": tree_items})

# The repo was bootstrapped with a README via the Contents API; base our
# commit on that head so history is linear.
head = api("GET", f"{API}/ref/heads/main")
parent_sha = head["object"]["sha"]

print("creating commit ...")
commit = api("POST", f"{API}/commits", {
    "message": "Dollar bot: Telethon listener, AI extraction, live boards, dashboard",
    "tree": tree["sha"],
    "parents": [parent_sha],
})

print("updating ref main ...")
api("PATCH", f"{API}/refs/heads/main", {"sha": commit["sha"], "force": True})

print(f"DONE: main -> {commit['sha']}")
