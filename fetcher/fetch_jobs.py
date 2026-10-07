#!/usr/bin/env python3
"""
Daily government-job collector (standard library only, no pip install needed).

1. Reads every RSS feed listed in feeds.json
2. For each new post, opens the post page and looks for an OFFICIAL link
   (gov.in / nic.in / board websites) -> used as the Apply link
3. Extracts details: organisation, category, vacancies, last date
4. Merges with the old data/jobs.json, removes old entries, saves.

Only a short summary + links are stored (no full article copying).
"""
import html
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "fetcher" / "feeds.json"
OUT = ROOT / "data" / "jobs.json"
UA = "Mozilla/5.0 (compatible; GovJobsFetcher/1.0; +https://github.com)"
TIMEOUT = 25

CATEGORIES = [
    ("Railway", r"\brailway|\brrb\b|\brrc\b|\bntpc\b.*railway|indian railways"),
    ("Banking", r"\bbank\b|\bibps\b|\bsbi\b|\brbi\b|\bnabard\b|\bgramin\b|\bcooperative bank"),
    ("SSC", r"\bssc\b|staff selection"),
    ("UPSC", r"\bupsc\b|union public service"),
    ("Defence", r"\barmy\b|\bnavy\b|air force|\bagniveer|\bcrpf\b|\bbsf\b|\bcisf\b|\bitbp\b|\bdrdo\b|\bdefence"),
    ("Police", r"\bpolice\b|\bconstable\b|\bsub[- ]inspector\b|\bsi\b recruitment"),
    ("Teaching", r"\bteacher\b|\btet\b|\bkvs\b|\bnvs\b|\bprofessor\b|\blecturer\b|\bschool\b"),
    ("Medical", r"\bnurs|\bdoctor\b|\bmedical officer|\baiims\b|\bhealth\b|\bpharmac"),
    ("PSC / State", r"\bpsc\b|\bpublic service commission|\bsubordinate service"),
    ("PSU", r"\bpsu\b|\bongc\b|\biocl\b|\bntpc\b|\bsail\b|\bbhel\b|\bcoal india|\bgail\b|\bhal\b|\bbel\b"),
]

STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa",
    "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala",
    "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland",
    "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal", "Delhi", "Jammu", "Kashmir",
    "Ladakh", "Chandigarh", "Puducherry",
]

MONTHS = ("jan feb mar apr may jun jul aug sep oct nov dec").split()


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        raw = r.read()
        charset = r.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def strip_tags(s):
    s = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", s or "")
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def tag_text(el, name):
    for child in el.iter():
        if child.tag.split("}")[-1] == name and child.text:
            return child.text
    return ""


def parse_feed(xml_text, source_name):
    items = []
    try:
        root = ET.fromstring(xml_text.lstrip())
    except ET.ParseError as e:
        print(f"  ! could not parse feed {source_name}: {e}")
        return items
    for it in root.iter():
        kind = it.tag.split("}")[-1]
        if kind not in ("item", "entry"):
            continue
        title = strip_tags(tag_text(it, "title"))
        link = tag_text(it, "link").strip()
        if not link:  # Atom style
            for c in it:
                if c.tag.split("}")[-1] == "link" and c.attrib.get("href"):
                    link = c.attrib["href"]
                    break
        desc = tag_text(it, "description") or tag_text(it, "summary") or tag_text(it, "encoded")
        pub = tag_text(it, "pubDate") or tag_text(it, "published") or tag_text(it, "updated")
        try:
            dt = parsedate_to_datetime(pub) if pub and "," in pub else datetime.fromisoformat(pub.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            dt = datetime.now(timezone.utc)
        if title and link:
            items.append({"title": title, "link": link, "desc_html": desc or "", "date": dt, "source": source_name})
    return items


def is_official(url, domains):
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in domains)


def find_links(page_html, post_url, domains):
    """Return (apply_link, notification_pdf, official_site) from a post page."""
    apply_link = notice_pdf = official_site = None
    post_host = (urlparse(post_url).hostname or "").lower()
    for m in re.finditer(r'(?is)<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page_html):
        href, label = m.group(1).strip(), strip_tags(m.group(2)).lower()
        if not href.startswith("http"):
            continue
        host = (urlparse(href).hostname or "").lower()
        if host == post_host or not is_official(href, domains):
            continue
        if not official_site:
            official_site = href
        if href.lower().split("?")[0].endswith(".pdf") and not notice_pdf:
            notice_pdf = href
        if not apply_link and re.search(r"apply|registration|online form|login", label + href.lower()):
            apply_link = href
    return apply_link, notice_pdf, official_site


def classify(text):
    low = text.lower()
    for name, pat in CATEGORIES:
        if re.search(pat, low):
            return name
    return "Other"


def find_state(text):
    for s in STATES:
        if re.search(r"\b" + re.escape(s) + r"\b", text, re.I):
            return "Jammu & Kashmir" if s in ("Jammu", "Kashmir") else s
    return "All India"


def find_vacancies(text):
    m = re.search(r"(\d[\d,]*)\s*(?:\+\s*)?(?:posts?|vacanc(?:y|ies)|openings?)", text, re.I)
    if m:
        return m.group(1).replace(",", "")
    m = re.search(r"(?:posts?|vacanc(?:y|ies))\D{0,12}(\d[\d,]*)", text, re.I)
    return m.group(1).replace(",", "") if m else ""


def find_last_date(text):
    pat = (
        r"last\s*date\D{0,30}?"
        r"(\d{1,2}(?:st|nd|rd|th)?[\s\-/.]+(?:\d{1,2}|" + "|".join(MONTHS) + r")[a-z]*[\s\-/.,]+\d{2,4})"
    )
    m = re.search(pat, text, re.I)
    return m.group(1).strip() if m else ""


def find_org(title):
    t = re.split(r"\s+(?:recruitment|notification|vacancy|vacancies|online form|apply)\b", title, maxsplit=1, flags=re.I)[0]
    t = re.sub(r"^\W+|\W+$", "", t)
    return t[:80]


def job_id(link):
    return re.sub(r"[^a-z0-9]+", "-", link.lower()).strip("-")[-80:]


def load_old():
    if OUT.exists():
        try:
            return json.loads(OUT.read_text(encoding="utf-8")).get("jobs", [])
        except Exception:
            pass
    return []


def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    domains = cfg["official_domains"]
    old = {j["id"]: j for j in load_old()}
    now = datetime.now(timezone.utc)
    new_count = 0

    for feed in cfg["feeds"]:
        print(f"Feed: {feed['name']}")
        try:
            items = parse_feed(http_get(feed["url"]), feed["name"])
        except Exception as e:
            print(f"  ! failed: {e}")
            continue
        print(f"  {len(items)} items")
        for it in items:
            jid = job_id(it["link"])
            if jid in old:
                continue
            summary_src = strip_tags(it["desc_html"])
            apply_link = notice_pdf = official_site = None
            page_text = ""
            try:
                page = http_get(it["link"])
                apply_link, notice_pdf, official_site = find_links(page, it["link"], domains)
                page_text = strip_tags(page)[:6000]
                time.sleep(1)  # be polite to the source site
            except Exception as e:
                print(f"  ! post page failed ({it['link']}): {e}")
            blob = f"{it['title']} {summary_src} {page_text}"
            best = apply_link or official_site
            old[jid] = {
                "id": jid,
                "title": it["title"],
                "organisation": find_org(it["title"]),
                "category": classify(it["title"] + " " + summary_src),
                "state": find_state(it["title"] + " " + summary_src),
                "vacancies": find_vacancies(blob),
                "last_date": find_last_date(blob),
                "summary": summary_src[:220].rstrip() + ("…" if len(summary_src) > 220 else ""),
                "posted": it["date"].astimezone(timezone.utc).strftime("%Y-%m-%d"),
                "apply_url": best or "",
                "notification_url": notice_pdf or "",
                "official": bool(best),
                "source_name": it["source"],
                "source_url": it["link"],
                "added": now.strftime("%Y-%m-%d"),
            }
            new_count += 1

    cutoff = (now - timedelta(days=cfg["max_age_days"])).strftime("%Y-%m-%d")
    jobs = [j for j in old.values() if j["posted"] >= cutoff]
    jobs.sort(key=lambda j: (j["posted"], j["added"]), reverse=True)
    jobs = jobs[: cfg["max_jobs_kept"]]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"generated_at": now.strftime("%Y-%m-%d %H:%M UTC"), "count": len(jobs), "jobs": jobs},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"Done. {new_count} new, {len(jobs)} total saved to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
