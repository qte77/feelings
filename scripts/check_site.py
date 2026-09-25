"""Headless check of the results page: light/dark x desktop/phone, failing on errors.

    uv run --directory ../polyfetch-scrape python ../feelings/scripts/check_site.py <out_dir> [url]

Uses polyfetch-scrape's patchright Chromium (see qte77/brand/ui-kit README). Checks the
layered page: the answer and ratings render, every <details> starts closed, deep links open
them, every chart draws once opened, the strictness slider updates, and nothing scrolls
sideways with everything open. Fails on console errors, page errors or failed requests;
saves a collapsed and an expanded screenshot per variant.
"""

import sys

from patchright.sync_api import sync_playwright

OUT = sys.argv[1]
URL = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8137/"
VIEWPORTS = (
    ("desktop", {"width": 1280, "height": 900}),
    ("phone", {"width": 390, "height": 844}),
)
problems = []


def expect(ok, message):
    if not ok:
        problems.append(message)


def watch(page, where):
    page.on(
        "console",
        lambda m: m.type == "error" and problems.append(f"{where} console: {m.text}"),
    )
    page.on("pageerror", lambda e: problems.append(f"{where} pageerror: {e}"))
    page.on(
        "requestfailed",
        lambda r: problems.append(f"{where} request failed: {r.url}"),
    )


def ready(page, url):
    page.goto(url, wait_until="networkidle")
    page.wait_for_selector("body[data-ready=true]")


with sync_playwright() as p:
    browser = p.chromium.launch()
    for theme in ("light", "dark"):
        for name, viewport in VIEWPORTS:
            where = f"{theme}/{name}"
            page = browser.new_page(viewport=viewport, device_scale_factor=1)
            watch(page, where)
            ready(page, f"{URL}?theme={theme}")

            verdict = page.locator("#verdict").inner_text()
            tiles = page.locator("#tiles > div").count()
            ratings = page.locator("#ratings li").count()
            opened = page.locator("details[open]").count()
            expect("labelled code changes" in verdict, f"{where}: no verdict")
            expect(tiles == 3, f"{where}: {tiles} tiles")
            expect(ratings == 4, f"{where}: {ratings} ratings")
            expect(opened == 0, f"{where}: {opened} sections open on load")
            page.screenshot(path=f"{OUT}/{theme}-{name}-collapsed.png", full_page=True)

            # Open every section, outer ones first, and check what they hold.
            for summary in page.locator("details > summary").all():
                summary.click()
            charts = page.evaluate(
                "[...document.querySelectorAll('canvas')].map(c => c.width)"
            )
            rows = {
                t: page.locator(f"#{t} tbody tr").count()
                for t in ("compare-table", "sized-table", "pilot-table", "sweep-table")
            }
            expect(
                all(w > 0 for w in charts) and len(charts) == 2,
                f"{where}: charts {charts}",
            )
            expect(
                rows
                == {
                    "compare-table": 4,
                    "sized-table": 2,
                    "pilot-table": 5,
                    "sweep-table": 9,
                },
                f"{where}: rows {rows}",
            )
            asked = [
                t for t in page.locator(".asked").all_inner_texts() if t.endswith("?”")
            ]
            expect(len(asked) == 4, f"{where}: {len(asked)} exact questions shown")
            version = page.locator("#version").inner_text()
            expect(bool(version.strip()), f"{where}: no version in the footer")
            expect(
                "Chart.js" not in page.locator("body").inner_text(),
                f"{where}: Chart.js still mentioned",
            )

            before = page.locator("#frr-value").inner_text()
            page.locator("#threshold").fill("0.5")
            after = page.locator("#frr-value").inner_text()
            setting = page.locator("#threshold-out").inner_text()
            expect(
                setting == "0.50" and after != before,
                f"{where}: slider {setting} {before!r} -> {after!r}",
            )

            overflow = page.evaluate(
                "document.documentElement.scrollWidth > window.innerWidth"
            )
            expect(not overflow, f"{where}: page scrolls sideways with everything open")
            page.screenshot(path=f"{OUT}/{theme}-{name}-expanded.png", full_page=True)
            print(
                f"{where}: tiles={tiles} ratings={ratings} closed_on_load={opened == 0} charts={charts} rows={rows} slider={setting}"
            )
            page.close()

    # Deep links open their section (and a nested one opens its parent too).
    # A fresh page per link: a second link on the same page only changes the hash.
    for anchor, wanted in (
        ("strictness", ["strictness"]),
        ("compare-chart", ["compare", "compare-chart"]),
    ):
        page = browser.new_page()
        watch(page, f"deeplink #{anchor}")
        ready(page, f"{URL}#{anchor}")
        opened = page.evaluate(
            "[...document.querySelectorAll('details[open]')].map(d => d.id)"
        )
        expect(sorted(opened) == sorted(wanted), f"deeplink #{anchor}: open {opened}")
        print(f"deeplink #{anchor}: open {opened}")
        page.close()
    page = browser.new_page()
    watch(page, "theme")
    ready(page, f"{URL}?theme=light")
    page.click("#theme-toggle")
    print(
        "theme after one click:",
        page.evaluate("document.documentElement.dataset.theme"),
    )
    browser.close()

print("PROBLEMS:", problems or "none")
sys.exit(1 if problems else 0)
