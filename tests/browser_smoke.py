"""Exercise the actual catalogue at a project subpath; no upstream browser requests."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import json
from datetime import datetime,timedelta
import tempfile
import threading
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

def main():
    screenshots=ROOT/'browser-checks';screenshots.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        shutil.copytree(ROOT/'dist',Path(temporary)/'example-tool')
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=temporary));threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1050});errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}/example-tool/')
                page.locator('#rows tr').first.wait_for(timeout=30000)
                assert page.locator('#rows tr').count()>0
                page.locator('#query').fill('25544')
                assert page.locator('#rows tr').count()==1
                page.locator('.object-name').click()
                assert 'ISS' in page.locator('#object-title').inner_text()
                assert 'CATNR=25544' in page.locator('#official').get_attribute('href')
                with page.expect_download() as download:
                    page.locator('#save').click()
                assert download.value.suggested_filename.endswith('.json')
                saved=Path(temporary)/'receipt.json';download.value.save_as(saved)
                capture=json.loads(saved.read_text());assert len(capture['rows'])>1000
                capture['capturedAt']=(datetime.fromisoformat(capture['capturedAt'].replace('Z','+00:00'))-timedelta(days=2)).isoformat().replace('+00:00','Z')
                capture['sourceUpdatedAt']=(datetime.fromisoformat(capture['sourceUpdatedAt'].replace('Z','+00:00'))-timedelta(days=2)).isoformat().replace('+00:00','Z')
                capture['rows'][0][1]='TEST PRIOR OBJECT NAME'
                saved.write_text(json.dumps(capture))
                page.locator('#import').set_input_files(str(saved))
                page.get_by_text('Imported locally into this tab.',exact=False).wait_for()
                page.locator('#capture').select_option(index=0)
                page.locator('#compare').click()
                page.locator('.change-summary').wait_for()
                assert 'Changed' in page.locator('.change-summary').inner_text()
                page.locator('#query').fill('<img src=x onerror=alert(1)>')
                assert page.locator('#rows tr').count()==0
                assert page.locator('img').count()==0
                page.locator('#reset').click();page.get_by_role('button',name='Canadian objects',exact=True).click()
                assert page.locator('#owner').input_value()=='CA'
                assert page.locator('#rows tr').count()>0
                page.locator('#reset').click();page.locator('#next').click()
                assert 'Page 2' in page.locator('#page-label').inner_text()
                page.screenshot(path=str(screenshots/'desktop.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile page overflows'
                page.screenshot(path=str(screenshots/'mobile.png'),full_page=True)
                assert not errors,errors
                browser.close()
            print('Browser passed: real snapshot, search/detail, export, safe text, custom owner, pagination and mobile layout')
        finally:server.shutdown()
if __name__=='__main__':main()
