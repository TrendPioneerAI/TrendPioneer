#!/usr/bin/env python3
"""WhenRest free: public sources only; never reads accounts or invents resets."""
from __future__ import annotations
import concurrent.futures
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'data.json'
UA = 'WhenRest/0.2 (+https://github.com/TrendPioneerAI/TrendPioneer/tree/main/whenrest)'
NOW = datetime.now(timezone.utc).isoformat()
SOURCES = {
    'codex-index': {'provider': 'codex', 'name': 'Codex Resets · 第三方公开索引', 'url': 'https://codex-resets.com/', 'kind': 'reset-index'},
    'openai-status': {'provider': 'codex', 'name': 'OpenAI 官方服务状态', 'url': 'https://status.openai.com/api/v2/summary.json', 'kind': 'service-status'},
    'claude-status': {'provider': 'claude', 'name': 'Claude 官方服务状态', 'url': 'https://status.claude.com/api/v2/summary.json', 'kind': 'service-status'},
    'cursor-status': {'provider': 'cursor', 'name': 'Cursor 官方服务状态', 'url': 'https://status.cursor.com/api/v2/summary.json', 'kind': 'service-status'},
}
DATE_RE = re.compile(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+20\d{2},?\s+\d{1,2}:\d{2}\s*[AP]M\s*(?:UTC|GMT)', re.I)
TWEET_RE = re.compile(r'^https://(?:www\.)?(?:x|twitter)\.com/[^/?#]+/status/(\d+)')


def get(url: str) -> requests.Response:
    response = requests.get(url, headers={'User-Agent': UA, 'Accept': 'text/html,application/json,text/plain'}, timeout=(8, 20))
    response.raise_for_status()
    if len(response.content) > 5_000_000:
        raise ValueError('source exceeds 5 MB safety limit')
    return response


def parse_time(card) -> str | None:
    node = card.find('time', datetime=True) or card.find(attrs={'data-timestamp': True})
    if node:
        raw = node.get('datetime') or node.get('data-timestamp')
        try:
            if re.fullmatch(r'\d{10,13}', str(raw)):
                value = float(raw) / (1000 if len(str(raw)) == 13 else 1)
                dt = datetime.fromtimestamp(value, timezone.utc)
            else:
                dt = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    return None
            return dt.astimezone(timezone.utc).isoformat()
        except (ValueError, OverflowError, OSError):
            pass
    match = DATE_RE.search(card.get_text(' ', strip=True))
    if match:
        value = re.sub(r'\s+', ' ', match.group(0)).replace(' GMT', ' UTC')
        for fmt in ('%b %d, %Y, %I:%M %p UTC', '%B %d, %Y, %I:%M %p UTC', '%b %d, %Y %I:%M %p UTC'):
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                pass
    return None


def parse_codex(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    result, seen = [], set()
    for link in soup.find_all('a', href=True):
        url = link['href']
        m = TWEET_RE.match(url)
        if not m:
            continue
        url = url.split('?')[0].split('#')[0]
        if url in seen:
            continue
        card = link
        for ancestor in link.parents:
            if ancestor.name in ('body', 'html', '[document]'):
                break
            tweet_urls = {a['href'].split('?')[0] for a in ancestor.find_all('a', href=True) if TWEET_RE.match(a['href'])}
            if len(tweet_urls) > 1:
                break
            card = ancestor
            if ancestor.name in ('li', 'article'):
                break
        text = card.get_text(' ', strip=True)
        if not re.search(r'reset', text, re.I):
            continue
        at = parse_time(card)
        time_method = 'source-page'
        if not at:
            # Twitter Snowflake IDs carry the post timestamp. This is the post time,
            # NOT the time a reset landed in an account.
            value = ((int(m.group(1)) >> 22) + 1288834974657) / 1000
            dt = datetime.fromtimestamp(value, timezone.utc)
            if dt.year < 2020 or dt > datetime.now(timezone.utc):
                continue
            at, time_method = dt.isoformat(), 'post-id-timestamp'
        lower = text.lower()
        kind, title = 'record', '重置相关公告记录'
        note = '公开索引收录的重置相关消息；请查看原帖确认范围、条件及到账情况。'
        if any(x in lower for x in ('kerfuffle', 'apologize', 'affected time window')):
            kind, title = 'compensation', '受影响用户的补偿重置记录'
            note = '可能仅涉及受影响的账户，并非全体用户自动刷新。具体资格请查看原帖。'
        elif any(x in lower for x in ('banked', 'reset bank', 'into your bank', 'into the bank')):
            kind, title = 'banked', '可保留重置相关公告'
            note = '涉及可保留重置；不代表额度已自动恢复。资格、领取和使用条件以原帖及账户为准。'
        elif re.search(r'(?:have|has|now|all|fully|limits)\s+(?:been\s+)?reset|reset\s+(?:usage|rate|limits)', lower):
            kind, title = 'automatic', '使用额度重置公告记录'
            note = '索引记录了一次额度重置公告；不能据此确定你的账户已到账。'
        plans = [p for p in ('Plus', 'Pro', 'Business', 'Team', 'Enterprise') if re.search(r'\b' + p + r'\b', text, re.I)]
        result.append({'id': 'codex-' + m.group(1), 'provider': 'codex', 'kind': kind, 'title': title, 'summary': note, 'publishedAt': at, 'timeMethod': time_method, 'sourceId': 'codex-index', 'sourceUrl': url, 'indexUrl': SOURCES['codex-index']['url'], 'evidence': 'third-party-index', 'plansMentioned': plans})
        seen.add(url)
    if not result:
        raise ValueError('未解析到带来源的重置记录，保留上次成功数据；可能是页面结构变化')
    return sorted(result, key=lambda item: item['publishedAt'], reverse=True)[:250]


def collect_index() -> dict:
    robots_url = 'https://codex-resets.com/robots.txt'
    response = requests.get(robots_url, headers={'User-Agent': UA}, timeout=(8, 12))
    if response.status_code == 200:
        robots = RobotFileParser()
        robots.parse(response.text.splitlines())
        if not robots.can_fetch('WhenRest', SOURCES['codex-index']['url']):
            raise PermissionError('来源 robots.txt 不允许采集，已停止此来源')
    elif response.status_code not in (404, 410):
        raise RuntimeError('无法核验来源 robots.txt: HTTP ' + str(response.status_code))
    response = get(SOURCES['codex-index']['url'])
    return {'events': parse_codex(response.text)}


def collect_status(source: dict) -> dict:
    payload = get(source['url']).json()
    if not isinstance(payload.get('components'), list) or not isinstance(payload.get('status'), dict):
        raise ValueError('官方状态接口结构异常')
    provider = source['provider']
    pattern = {'codex': r'codex', 'claude': r'claude code|claude\.ai', 'cursor': r'IDE|CLI|Cloud Agents|cursor\.com'}[provider]
    components = [{'name': str(c.get('name', ''))[:120], 'status': str(c.get('status', 'unknown'))[:40], 'updatedAt': c.get('updated_at')} for c in payload['components'] if re.search(pattern, str(c.get('name', '')), re.I)]
    overall = 'unknown' if not components else ('operational' if all(c['status'] == 'operational' for c in components) else 'degraded')
    return {'service': {'provider': provider, 'status': overall, 'components': components, 'sourceUpdatedAt': payload.get('page', {}).get('updated_at'), 'pageUrl': source['url'].split('/api/')[0], 'note': '仅为服务运行状态，不是额度或重置证明。'}}


def main() -> None:
    try:
        previous = json.loads(OUT.read_text(encoding='utf-8'))
    except (FileNotFoundError, ValueError):
        previous = {'events': [], 'sources': [], 'services': []}
    old_sources = {s['id']: s for s in previous.get('sources', [])}
    services = {s['provider']: s for s in previous.get('services', [])}
    events = {e['id']: e for e in previous.get('events', [])}
    states = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {pool.submit(collect_index if sid == 'codex-index' else collect_status, *(() if sid == 'codex-index' else (meta,))): (sid, meta) for sid, meta in SOURCES.items()}
        for future in concurrent.futures.as_completed(jobs):
            sid, meta = jobs[future]
            record = {'id': sid, **meta, 'attemptedAt': NOW, 'lastSuccessAt': old_sources.get(sid, {}).get('lastSuccessAt')}
            try:
                value = future.result()
                record.update(status='ok', lastSuccessAt=NOW, error=None)
                for event in value.get('events', []):
                    event['firstSeenAt'] = events.get(event['id'], {}).get('firstSeenAt', NOW)
                    event['lastSeenAt'] = NOW
                    events[event['id']] = event
                if 'service' in value:
                    services[meta['provider']] = {**value['service'], 'sourceId': sid, 'fetchedAt': NOW}
                record['items'] = len(value.get('events', value.get('service', {}).get('components', [])))
            except Exception as exc:
                record.update(status='error', error=(type(exc).__name__ + ': ' + str(exc))[:300])
            states.append(record)
            print(json.dumps(record, ensure_ascii=False))
    data = {'version': 2, 'generatedAt': NOW, 'pollIntervalSeconds': 300, 'refreshNote': '后台目标每 5 分钟采集；免费调度可能延迟。网页每 60 秒检查一次。', 'sources': sorted(states, key=lambda s: s['id']), 'events': sorted(events.values(), key=lambda e: e['publishedAt'], reverse=True)[:250], 'services': list(services.values()), 'coverage': {'codex': 'third-party-reset-index-and-official-service-status', 'claude': 'official-service-status-only', 'cursor': 'official-service-status-only', 'gemini': 'documented-daily-api-rule-only', 'kimi': 'not-connected'}}
    with tempfile.NamedTemporaryFile(mode='w', dir=ROOT, encoding='utf-8', delete=False) as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        temp = stream.name
    os.replace(temp, OUT)
    print('WHENREST_RESULT', json.dumps({'successfulSources': sum(s['status'] == 'ok' for s in states), 'totalSources': len(states), 'resetRecords': len(events), 'generatedAt': NOW}))
    if not any(s['status'] == 'ok' for s in states):
        print('WARNING: all sources failed; error states and last-known records were preserved.')


if __name__ == '__main__':
    main()
