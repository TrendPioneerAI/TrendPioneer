"""Exercise public pages without replacing network requests with mocks."""
import json
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright

OUT = Path('whenrest-test')
OUT.mkdir(exist_ok=True)
CANDIDATES = [
    'https://rawcdn.githack.com/TrendPioneerAI/TrendPioneer/1d353bf2d06646f150689bade76a8dfb53a83fc6/whenrest/index.html',
    'https://raw.githack.com/TrendPioneerAI/TrendPioneer/main/whenrest/index.html',
]
report = {'checks': [], 'probes': []}
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, timezone_id='Asia/Shanghai')
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    selected = None
    for i, url in enumerate(CANDIDATES):
        probe = {'url': url}
        try:
            r = requests.get(url, timeout=30)
            probe.update(httpStatus=r.status_code, contentType=r.headers.get('content-type'), correctTitle='<title>WhenRest' in r.text)
            response = page.goto(url, wait_until='domcontentloaded', timeout=45000)
            probe.update(browserStatus=response.status if response else None, browserUrl=page.url, browserTitle=page.title())
            # The provider shows a standard content notice for ALL HTML files.
            # Use the normal visible button to open our known, public file.
            if page.title() == 'External Content Notice | rawgit.hack':
                assert page.url == url
                page.get_by_text('Open the page', exact=True).click()
                probe['contentNoticeConfirmed'] = True
            page.wait_for_selector('#eventcount', timeout=20000)
            page.wait_for_function("!!document.getElementById('eventcount') && /^\\d+$/.test(document.getElementById('eventcount').textContent.trim())", timeout=30000)
            assert int(page.locator('#eventcount').inner_text()) > 0
            selected = url
            probe['browserLiveData'] = True
            report['probes'].append(probe)
            break
        except Exception as exc:
            probe.update(error=str(exc)[:1000], browserTitle=page.title(), body=page.locator('body').inner_text()[:2200], jsErrors=errors[:10])
            page.screenshot(path=str(OUT / f'probe-{i}.png'), full_page=True)
            report['probes'].append(probe)
            print('PROBE', json.dumps(probe, ensure_ascii=False))
    try:
        assert selected, 'Neither public endpoint loaded the live dashboard in a real browser.'
        report['publicUrl'] = selected
        report['checks'].append({'name': 'Public URL renders the dashboard and fetches live JSON', 'ok': True, 'records': int(page.locator('#eventcount').inner_text())})
        report['sourceHealth'] = page.locator('#health').inner_text()
        assert page.locator('#source-list article').count() == 4
        report['checks'].append({'name': 'Four public sources with explicit health states', 'ok': True})
        page.screenshot(path=str(OUT / 'desktop.png'), full_page=True)
        page.locator('#provider').select_option('claude')
        assert '尚未接入' in page.locator('#events').inner_text()
        page.locator('#provider').select_option('all')
        page.locator('#kind').select_option('banked')
        assert page.locator('#events article').count() > 0
        page.locator('#kind').select_option('all')
        page.locator('#search').fill('Business')
        assert page.locator('#events article').count() > 0
        page.locator('#search').fill('')
        report['checks'].append({'name': 'Provider, reset type and plan-name filters', 'ok': True})
        page.locator('[data-act="add"]').first.click()
        page.locator('#timer-name').fill('验收测试 · 个人额度')
        page.locator('#timer-form button[type=submit]').click()
        assert '验收测试' in page.locator('#timers').inner_text()
        page.reload(wait_until='domcontentloaded')
        page.wait_for_selector('#timers [data-act=delete]', timeout=20000)
        assert '验收测试' in page.locator('#timers').inner_text()
        with page.expect_download() as download:
            page.locator('#timers [data-act=calendar]').click()
        download.value.save_as(str(OUT / 'test-calendar.ics'))
        page.locator('#timers [data-act=delete]').click()
        report['checks'].append({'name': 'Personal timer persistence, calendar export and deletion', 'ok': True})
        for iso, expected in [('2026-03-08T07:00:00Z','2026-03-08T08:00:00.000Z'),('2026-03-08T09:00:00Z','2026-03-09T07:00:00.000Z'),('2026-11-01T08:00:00Z','2026-11-02T08:00:00.000Z')]:
            actual = page.evaluate('(iso)=>new Date(window.WhenRestTest.midnight(Date.parse(iso))).toISOString()', iso)
            assert actual == expected, (iso, actual, expected)
        report['checks'].append({'name': 'Pacific-midnight daylight-saving transitions', 'ok': True})
        page.wait_for_function("!!document.getElementById('eventcount') && /^\\d+$/.test(document.getElementById('eventcount').textContent.trim())", timeout=30000)
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile horizontal overflow'
        page.screenshot(path=str(OUT / 'mobile.png'), full_page=True)
        report['checks'].append({'name': '390px mobile viewport without horizontal overflow', 'ok': True})
        report['javascriptErrors'] = errors
        assert not errors, errors
        report['checks'].append({'name': 'No uncaught JavaScript errors', 'ok': True})
        report['success'] = True
    finally:
        (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print('WHENREST_VERIFICATION', json.dumps(report, ensure_ascii=False))
        browser.close()
