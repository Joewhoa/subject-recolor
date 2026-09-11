"""Actual system-curl multipart integration against a localhost fake API. No paid/network API."""
from __future__ import annotations
import base64, io, json, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from PIL import Image
from recolor.api.image_edit_client import ImageEditClient
from recolor.config import Settings

class Handler(BaseHTTPRequestHandler):
    response_png = b""
    received = b""
    request_id = ""
    def do_POST(self):
        length = int(self.headers.get("content-length", "0"))
        type(self).received = self.rfile.read(length)
        type(self).request_id = self.headers.get("x-client-request-id", "")
        payload = json.dumps({"model":"fake-curl-model","data":[{"b64_json":base64.b64encode(type(self).response_png).decode()}]}).encode()
        self.send_response(200); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(payload))); self.end_headers(); self.wfile.write(payload)
    def log_message(self, *_args): pass

class CurlLocalIntegration(unittest.TestCase):
    def test_actual_curl_multipart_to_local_fake_api(self):
        with TemporaryDirectory() as temp:
            source=Path(temp)/"upload.jpg"; Image.new("RGB",(80,60),(1,2,3)).save(source)
            out=io.BytesIO(); Image.new("RGB",(64,48),(4,5,6)).save(out,"PNG"); Handler.response_png=out.getvalue()
            server=HTTPServer(("127.0.0.1",0),Handler); thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
            try:
                settings=Settings(base_url=f"http://127.0.0.1:{server.server_port}",read_timeout=30,context_workers=1)
                result=ImageEditClient(settings,"fake-key").edit(source,"本地假提示词","local-request-id")
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=5)
            self.assertEqual(result.image_bytes,Handler.response_png)
            self.assertEqual(result.metadata["transport"],"system-curl")
            self.assertEqual(Handler.request_id,"local-request-id")
            self.assertIn(b'name="model"',Handler.received)
            self.assertIn(b'gpt-image-2',Handler.received)
            self.assertIn(b'name="prompt"',Handler.received)
            self.assertIn(b'name="image"',Handler.received)
            self.assertIn(b'name="response_format"',Handler.received)

if __name__=="__main__": unittest.main()
