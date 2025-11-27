
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re

def is_javascript_type(type_attr: str) -> bool:
    if not type_attr:
        return True
    type_norm = type_attr.split(";", 1)[0].strip().lower()
    if not type_norm or type_norm == "module":
        return True
    return type_norm in {
        "text/javascript", "application/javascript", "application/ecmascript",
        "text/ecmascript", "application/x-javascript", "application/x-ecmascript",
        "text/js"
    } or type_norm.endswith("+javascript")

def fetch_html(url: str) -> str | None:
    try:
        r = requests.get(url, timeout=20, allow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        return r.text if r.ok else None
    except Exception:
        return None

def fetch_js(url: str) -> str | None:
    try:
        r = requests.get(url, timeout=20, allow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*"
        })
        if not r.ok:
            return None
        ct = (r.headers.get("content-type") or "").lower()
        txt = r.text
        if "text/html" in ct or re.search(r"^\s*<!doctype html|^\s*<html", txt, re.I):
            return None
        return txt
    except Exception:
        return None

def collect_scripts(page_url: str):
    html = fetch_html(page_url)
    scripts = []
    if not html:
        return scripts
    soup = BeautifulSoup(html, "html.parser")
    idx = 0
    for tag in soup.find_all("script"):
        type_attr = (tag.get("type") or "").strip()
        if not is_javascript_type(type_attr):
            continue
        is_module = (type_attr.lower() == "module")
        src = tag.get("src")
        if src:
            abs_url = urljoin(page_url, src)
            code = fetch_js(abs_url)
            if code is None:
                continue
            idx += 1
            scripts.append({
                "id": str(idx),
                "kind": "external",
                "url": abs_url,
                "code": code,
                "module": is_module
            })
        else:
            code = tag.string or tag.text or ""
            if code.strip():
                idx += 1
                scripts.append({
                    "id": f"inline-{idx}",
                    "kind": "inline",
                    "url": f"inline://script-{idx}.js",
                    "code": code,
                    "module": is_module
                })
    return scripts
