import csv
import gzip
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from refresh import FIELDS, parse_csv, validate_config, collect
ROOT=Path(__file__).resolve().parents[1]

def config():
    result=json.loads((ROOT/'web/config.json').read_text())
    result['minimumRecords']=1
    return result

def source(records):
    output=io.StringIO();writer=csv.DictWriter(output,fieldnames=FIELDS);writer.writeheader()
    for data in records:
        row={key:'' for key in FIELDS};row.update(NORAD_CAT_ID='25544',OBJECT_NAME='ISS',OBJECT_TYPE='PAY',OWNER='ISS',LAUNCH_DATE='1998-11-20');row.update(data);writer.writerow(row)
    return output.getvalue().encode()

class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);(self.root/'web').mkdir();(self.root/'web/config.json').write_text(json.dumps(config()))
    def test_expanded_owners_and_large_catalogue_numbers(self):
        settings=config();settings['coverage']['owners']=['CA','NEW'];rows,total=parse_csv(source([{'NORAD_CAT_ID':'100000','OWNER':'CA'},{'NORAD_CAT_ID':'999999999','OWNER':'NEW'},{'NORAD_CAT_ID':'2','OWNER':'US'}]),settings)
        self.assertEqual(total,3);self.assertEqual(len(rows),2);self.assertEqual(rows[-1][0],'999999999')
    def test_bad_or_truncated_source_is_rejected(self):
        for body in [b'<html>error</html>',source([{},{}]),source([{'NORAD_CAT_ID':'0'}]),source([{'LAUNCH_DATE':'not a date'}]),source([{'LAUNCH_DATE':'2026-99-99'}]),source([{'PERIOD':'NaN'}])]:
            with self.assertRaises(ValueError):parse_csv(body,config())
    def test_capture_roundtrip_and_unchanged_edition_avoids_csv_download(self):
        calls=[]
        def fetch(url,limit):calls.append(url);return source([{}])
        with patch('refresh.now',return_value='2026-11-23T10:00:00Z'):
            result=collect(self.root,'2026-11-22 21:56:02 UTC',fetch)
        entry=result['captures'][0];data=json.loads(gzip.decompress((self.root/'web/data'/entry['file']).read_bytes()));self.assertEqual(data['rows'][0][0],'25544');self.assertEqual(data['sourceUpdatedAt'],'2026-11-22T21:56:02Z')
        with patch('refresh.now',return_value='2026-11-24T10:00:00Z'):
            result=collect(self.root,'2026-11-22 21:56:02 UTC',fetch)
        self.assertEqual(len(calls),1);self.assertEqual(len(result['captures']),1)
    def test_failed_refresh_keeps_index_and_capture(self):
        collect(self.root,'2026-11-22 21:56:02 UTC',lambda *_:source([{}]));path=self.root/'web/data/index.json';before=path.read_bytes()
        with self.assertRaises(ValueError):collect(self.root,'2026-11-23 21:56:02 UTC',lambda *_:b'broken')
        self.assertEqual(path.read_bytes(),before)
    def test_retention_and_changed_coverage_keep_old_capture_valid(self):
        settings=config();settings['retainedCaptures']=2;(self.root/'web/config.json').write_text(json.dumps(settings))
        for day in [21,22,23]:
            with patch('refresh.now',return_value=f'2026-11-{day}T10:00:00Z'):
                result=collect(self.root,f'2026-11-{day} 09:00:00 UTC',lambda *_:source([{}]))
        self.assertEqual(len(result['captures']),2);self.assertEqual(len(list((self.root/'web/data/captures').glob('*.gz'))),2)
        self.assertEqual(result['captures'][-1]['sourceUpdatedAt'],'2026-11-22T09:00:00Z')
    def test_invalid_settings_fail_before_network(self):
        for key,value in [('retainedCaptures',1),('minimumRecords',0),('maxSourceBytes',99),('comparisonFields',['bad'])]:
            settings=config();settings[key]=value
            with self.assertRaises(ValueError):validate_config(settings)
    def test_unexpected_large_shrink_keeps_last_good(self):
        collect(self.root,'2026-11-22 21:56:02 UTC',lambda *_:source([{'NORAD_CAT_ID':str(i)} for i in range(1,11)]))
        with self.assertRaisesRegex(ValueError,'shrank'):collect(self.root,'2026-11-23 21:56:02 UTC',lambda *_:source([{}]))
if __name__=='__main__':unittest.main()
