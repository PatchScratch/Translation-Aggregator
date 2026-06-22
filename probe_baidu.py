import httpx
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://fanyi.baidu.com/",
}

c = httpx.Client(follow_redirects=True, timeout=15, headers=headers)
r = c.get("https://fanyi.baidu.com/")
html = r.text

print("=== HOMEPAGE ===")
print("status:", r.status_code)
print("BAIDUID:", c.cookies.get("BAIDUID"))
print("len html:", len(html))

# Find all script sources
scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html, re.I)
print("\n=== SCRIPT SRCS (first 20) ===")
for s in scripts[:20]:
    print(s)

# Also look for any inline script that might set gtk now
inline_gtk = re.search(r'gtk\s*[:=]\s*["\']([^"\']+)["\']', html, re.I)
print("\ninline gtk in html:", inline_gtk.group(1) if inline_gtk else "NONE")

# Try to find any JS file that looks like the main bundle
main_js = None
for s in scripts:
    if "main" in s.lower() or "common" in s.lower() or "translate" in s.lower() or s.endswith(".js"):
        if s.startswith("//"):
            s = "https:" + s
        elif s.startswith("/"):
            s = "https://fanyi.baidu.com" + s
        main_js = s
        break

print("\nTrying first promising JS:", main_js)

if main_js:
    try:
        jr = c.get(main_js, timeout=15)
        jstext = jr.text
        print("JS len:", len(jstext))
        # Search for gtk inside the JS
        m = re.search(r'gtk\s*[:=]\s*["\']([^"\']+)["\']', jstext, re.I)
        print("gtk in JS:", m.group(1) if m else "NOT FOUND in this JS")

        # Also search for token
        m2 = re.search(r'token\s*[:=]\s*["\']([^"\']{10,})["\']', jstext, re.I)
        print("token in JS:", m2.group(1)[:30] if m2 else "NOT FOUND")

        # Sometimes it's stored as a variable like e = "320305.131321201"
        m3 = re.search(r'["\']([0-9]{5,}\.[0-9]{5,})["\']', jstext)
        print("possible numeric gtk pattern:", m3.group(1) if m3 else "NO")
    except Exception as e:
        print("Failed to fetch JS:", e)

# Try a few known alternative endpoints that scrapers use
print("\n=== TRYING ALTERNATIVE ENDPOINTS ===")

# 1. The old v2transapi without sign (will probably fail)
try:
    r1 = c.post("https://fanyi.baidu.com/v2transapi", data={
        "from": "en", "to": "zh", "query": "hello", "transtype": "realtime", "simple_means_flag": "3"
    })
    print("v2transapi (no sign) status:", r1.status_code, "len:", len(r1.text), "body[:200]:", repr(r1.text[:200]))
except Exception as e:
    print("v2transapi error:", e)

# 2. The trans/web one
try:
    r2 = c.post("https://fanyi.baidu.com/transapi/trans/web", data={
        "from": "en", "to": "zh", "query": "hello world", "source": "txt"
    })
    print("trans/web status:", r2.status_code, "len:", len(r2.text), "body[:300]:", repr(r2.text[:300]))
except Exception as e:
    print("trans/web error:", e)

# 3. A newer endpoint some people use: /ait/text/translate (POST json)
try:
    r3 = c.post("https://fanyi.baidu.com/ait/text/translate", json={
        "query": "hello world",
        "from": "en",
        "to": "zh",
        "reference": "",
        "corpusIds": [],
        "domain": "common",
        "milliTimestamp": 1234567890000
    }, headers={"Content-Type": "application/json", "Referer": "https://fanyi.baidu.com/"})
    print("ait/text/translate status:", r3.status_code, "len:", len(r3.text), "body[:400]:", repr(r3.text[:400]))
except Exception as e:
    print("ait error:", e)

print("\nDone probe.")
