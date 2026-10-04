"""Runtime regression checks without downloading or executing AI models."""
import concurrent.futures
import http.client
import json
import sys
import threading
import time
import types
import unittest
from unittest.mock import patch

import server
import model_runtime


class RuntimeTests(unittest.TestCase):
    def test_vision_failure_never_reports_a_ready_draft(self):
        from PIL import Image
        image = Image.new("RGB", (16, 16))
        with patch("server.generate_vision", side_effect=RuntimeError("model unavailable")):
            result = server.analyze_photo_bytes(image)
            self.assertFalse(result["success"])
            self.assertEqual(result["candidate_foods"], [])
        with patch("server.generate_vision", return_value=[{"generated_text": "not JSON"}]):
            result = server.analyze_photo_bytes(image)
            self.assertFalse(result["success"])
            self.assertFalse(result["parse_valid"])
            self.assertIn("enter foods manually", result["status"])

    def test_concurrent_load_and_failure_recovery(self):
        torch = types.SimpleNamespace(
            set_num_threads=lambda _: None,
            cuda=types.SimpleNamespace(is_available=lambda: False),
            backends=types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: False)),
            bfloat16="bfloat16", float32="float32", float16="float16",
        )
        for getter, cache in ((server.get_pipeline, "text"), (server.get_vision_pipeline, "vision")):
            with self.subTest(cache=cache):
                calls = []
                sentinel = object()

                def load(*args, **kwargs):
                    calls.append(1)
                    time.sleep(0.02)
                    return sentinel

                transformers = types.SimpleNamespace(pipeline=load)
                with patch("cpu_model.cpu_text_components", return_value={"model": "mock", "tokenizer": "mock"}), patch.dict(sys.modules, torch=torch, transformers=transformers), patch.dict(model_runtime._PIPES, {cache: None}), patch.dict(model_runtime._STATE, {cache: {"loading": False, "ready": False, "loaded_model": None, "error": None}}):
                    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                        results = list(pool.map(lambda _: getter(), range(8)))
                    self.assertEqual(len(calls), 1)
                    self.assertTrue(all(result is sentinel for result in results))
                    self.assertFalse(model_runtime._STATE[cache]["loading"])
                    model_runtime._PIPES[cache] = None
                    transformers.pipeline = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("load failed"))
                    with self.assertRaises(RuntimeError):
                        getter()
                    self.assertFalse(model_runtime._STATE[cache]["loading"])
                    transformers.pipeline = load
                    self.assertIs(getter(), sentinel)

    def test_request_validation(self):
        httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.NutriGuideHandler)
        worker = threading.Thread(target=httpd.serve_forever, daemon=True)
        worker.start()
        try:
            for body, headers, expected in (
                (b"[]", {}, 400),
                (b"\xff", {}, 400),
                (b"", {"Content-Length": "-1"}, 400),
                (b"", {"Content-Length": str(server.MAX_REQUEST_BYTES + 1)}, 413),
                (json.dumps({"age_months": 12, "question": 3}).encode(), {}, 400),
                (json.dumps({"age_months": 12, "question": "Food variety", "use_model": False}).encode(), {}, 200),
            ):
                connection = http.client.HTTPConnection(*httpd.server_address, timeout=3)
                try:
                    connection.request("POST", "/api/query", body, headers)
                    response = connection.getresponse()
                    self.assertEqual(response.status, expected)
                    json.loads(response.read())
                finally:
                    connection.close()
            for record, expected_status, expected_result in (
                ({"age_months": True}, 400, None),
                ({"age_months": 10, "red_flags": ["active_choking"]}, 200, "PROFESSIONAL_REVIEW_FLAG"),
                ({"age_months": 10, "confirmed": False}, 200, "INSUFFICIENT_DATA"),
                ({"age_months": 10, "confirmed": True, "recall_complete": True,
                  "breastfed": True, "solid_feeds": 3,
                  "daily_groups": ["Breast milk", "Grains, roots and tubers", "Pulses, nuts and seeds", "Eggs", "Other fruits and vegetables"]},
                 200, "INDICATORS_MET"),
            ):
                connection = http.client.HTTPConnection(*httpd.server_address, timeout=3)
                try:
                    connection.request("POST", "/api/screen-intake", json.dumps(record))
                    response = connection.getresponse()
                    self.assertEqual(response.status, expected_status)
                    result = json.loads(response.read())
                    if expected_result:
                        self.assertEqual(result["screening_result"], expected_result)
                finally:
                    connection.close()
        finally:
            httpd.shutdown()
            httpd.server_close()
            worker.join()


if __name__ == "__main__":
    unittest.main()
