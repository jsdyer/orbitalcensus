#!/usr/bin/env python3
"""Retain a validated, dated SATCAT capture; one directory check and at most one CSV request."""
import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
from urllib.request import Request, build_opener, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'https://celestrak.org/pub/satcat.csv'
DIRECTORY = 'https://celestrak.org/satcat/jsonDir.php'
FIELDS = ['NORAD_CAT_ID', 'OBJECT_NAME', 'OBJECT_ID', 'OBJECT_TYPE', 'OPS_STATUS_CODE', 'OWNER', 'LAUNCH_DATE', 'LAUNCH_SITE', 'DECAY_DATE', 'PERIOD', 'INCLINATION', 'APOGEE', 'PERIGEE', 'RCS', 'DATA_STATUS_CODE', 'ORBIT_CENTER', 'ORBIT_TYPE']
REQUIRED = set(FIELDS)
SCHEMA = 'coolcode.orbitalcensus.v1'

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')

def get(url, maximum):
    request = Request(url, headers={'User-Agent': 'CoolCode Orbital Census (+https://coolcode.ca/orbitalcensus/)', 'Accept-Encoding': 'gzip', 'Accept': 'text/csv,application/json,application/octet-stream'})
    # Deliberately no retries and no redirect following: provider asks clients to stop on errors.
    with build_opener(NoRedirect).open(request, timeout=45) as response:
        if response.status != 200:
            raise ValueError(f'Source returned HTTP {response.status}; stopped without retry')
        raw = response.read(maximum + 1)
        if len(raw) > maximum:
            raise ValueError('Source exceeds configured byte limit')
        if response.headers.get('Content-Encoding', '').lower() == 'gzip':
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as compressed:
                raw = compressed.read(maximum + 1)
        if len(raw) > maximum:
            raise ValueError('Decoded source exceeds configured byte limit')
        return raw

def validate_config(config):
    if not 2 <= config.get('retainedCaptures', 0) <= 60:
        raise ValueError('retainedCaptures must be 2–60')
    if not 1024 <= config.get('maxSourceBytes', 0) <= 50_000_000:
        raise ValueError('maxSourceBytes must be 1 KB–50 MB')
    if not 1 <= config.get('minimumRecords', 0) <= 500_000:
        raise ValueError('minimumRecords must be positive')
    if not 0 < config.get('minimumRetainedFraction', 0) <= 1:
        raise ValueError('minimumRetainedFraction must be greater than zero and at most one')
    for key in ('owners', 'objectTypes'):
        if not isinstance(config.get('coverage', {}).get(key), list) or not all(isinstance(v, str) and v for v in config['coverage'][key]):
            raise ValueError(f'coverage.{key} must be an array of codes; empty means all')
    if set(config['coverage']['objectTypes']) - {'PAY','R/B','DEB','UNK'}:
        raise ValueError('Unknown coverage object type')
    fields = config.get('comparisonFields')
    if not isinstance(fields, list) or not fields or set(fields) - REQUIRED or len(set(fields)) != len(fields):
        raise ValueError('comparisonFields must contain unique SATCAT fields')
    return config

def parse_csv(raw, config):
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
        raise ValueError('SATCAT columns changed or response is not the expected CSV')
    rows, ids = [], set()
    total = 0
    for row in reader:
        total += 1
        identifier = (row.get('NORAD_CAT_ID') or '').strip()
        if not re.fullmatch(r'[1-9]\d{0,8}', identifier) or identifier in ids:
            raise ValueError('Invalid or duplicate NORAD catalogue number')
        ids.add(identifier)
        if not row.get('OBJECT_NAME') or row.get('OBJECT_TYPE') not in {'PAY','R/B','DEB','UNK'}:
            raise ValueError('Missing name or unknown object type')
        if None in row or any(row.get(field) is None for field in FIELDS):
            raise ValueError('Incomplete SATCAT row')
        for field in ('LAUNCH_DATE', 'DECAY_DATE'):
            value = row[field].strip()
            if value and not re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:[T ][0-9:.Z+-]+)?', value):
                raise ValueError('Invalid catalogue date')
            if value:
                datetime.fromisoformat(value.replace('Z', '+00:00'))
        for field in ('PERIOD', 'INCLINATION', 'APOGEE', 'PERIGEE', 'RCS'):
            value = row[field].strip()
            if value and not math.isfinite(float(value)):
                raise ValueError('Invalid numeric catalogue field')
        if config['coverage']['owners'] and row['OWNER'] not in config['coverage']['owners']:
            continue
        if config['coverage']['objectTypes'] and row['OBJECT_TYPE'] not in config['coverage']['objectTypes']:
            continue
        rows.append([row[field].strip() for field in FIELDS])
    if total < config['minimumRecords']:
        raise ValueError(f'Only {total} catalogue rows; refusing suspected partial data')
    rows.sort(key=lambda row: int(row[0]))
    return rows, total

def atomic_json(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)

def collect(root=ROOT, source_stamp=None, fetch=get):
    config = validate_config(json.loads((root/'web/config.json').read_text()))
    base = root/'web/data'
    base.mkdir(parents=True, exist_ok=True)
    (base/'captures').mkdir(exist_ok=True)
    path = base/'index.json'
    index = json.loads(path.read_text()) if path.exists() else {'schema': SCHEMA, 'captures': []}
    captured = now()
    # Avoid frequent manual workflow requests too, including directory checks.
    prior_check = index.get('checkedAt')
    if prior_check and source_stamp is None:
        elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(prior_check.replace('Z','+00:00'))).total_seconds()
        if elapsed < 3600:
            print('A successful source check is less than one hour old; no network request made.')
            return index
    if source_stamp is None:
        entries = json.loads(fetch(DIRECTORY, 100_000))
        match = next((entry for entry in entries if entry.get('FILE_NAME') == 'satcat.csv'), None)
        if not match or not isinstance(match.get('FILE_MTIME'), str):
            raise ValueError('SATCAT directory schema changed')
        source_stamp = match['FILE_MTIME']
    updated = datetime.strptime(source_stamp, '%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=timezone.utc).isoformat().replace('+00:00','Z')
    coverage = config['coverage']
    latest = index['captures'][0] if index['captures'] else None
    if latest and latest['sourceUpdatedAt'] == updated and latest['coverage'] == coverage:
        index['checkedAt'] = captured
        atomic_json(path,index)
        print('Source edition unchanged; no CSV download.')
        return index
    raw = fetch(SOURCE, config['maxSourceBytes'])
    rows,total = parse_csv(raw, config)
    if latest and total < latest['sourceRecordCount'] * config['minimumRetainedFraction']:
        raise ValueError('Source catalogue shrank unexpectedly; keep last good capture and investigate')
    digest = hashlib.sha256(raw).hexdigest()
    filename = captured.replace(':','').replace('-','')+'-'+digest[:10]+'.json.gz'
    receipt = {'schema':SCHEMA,'capturedAt':captured,'sourceUpdatedAt':updated,'source':SOURCE,'sourceSha256':digest,'sourceRecordCount':total,'coverage':coverage,'fields':FIELDS,'rows':rows}
    body = json.dumps(receipt,ensure_ascii=False,separators=(',',':')).encode()
    target = base/'captures'/filename
    temporary = target.with_suffix('.tmp')
    temporary.write_bytes(gzip.compress(body,compresslevel=9,mtime=0))
    temporary.replace(target)
    entry = {key:receipt[key] for key in ['capturedAt','sourceUpdatedAt','sourceRecordCount','sourceSha256','coverage']}
    entry.update(file='captures/'+filename,recordCount=len(rows),bytes=target.stat().st_size)
    index.update(checkedAt=captured,source=SOURCE,captures=([entry]+index['captures'])[:config['retainedCaptures']])
    atomic_json(path,index)
    kept = {entry['file'] for entry in index['captures']}
    for old in (base/'captures').glob('*.json.gz'):
        if 'captures/'+old.name not in kept:
            old.unlink()
    print(f'Retained {len(rows):,} of {total:,} source objects, {target.stat().st_size:,} compressed bytes; source {updated}')
    return index

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-stamp', help='Known FILE_MTIME from a directory response already fetched this hour (initial capture only)')
    args = parser.parse_args()
    try:
        collect(source_stamp=args.source_stamp)
    except Exception as error:
        raise SystemExit(f'Capture failed; last good published data remains unchanged: {error}')
