import pytest
pytestmark = pytest.mark.skip(reason="Legacy docs/scraper test – skipped in CI")

import unittest
import os
import json
import shutil
from scraper.json_extractor import JsonExtractor

class TestJsonExtractor(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_cache"
        os.makedirs(self.test_dir, exist_ok=True)
        self.extractor = JsonExtractor(cache_dir=self.test_dir)

    def tearDown(self):
        # Rensa testfiler och kataloger
        self.extractor.cleanup()
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_extract_json_from_html(self):
        test_html = '''
        <html>
            <script type="application/json">
                {"test": "data"}
            </script>
            <pre>
                {"another": "object"}
            </pre>
        </html>
        '''
        results = self.extractor.extract_json_from_html(test_html)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], {"test": "data"})
        self.assertEqual(results[1], {"another": "object"})

    def test_html_entities(self):
        test_html = '''
        <script>
            {"special": "&quot;quoted&quot;"}
        </script>
        '''
        results = self.extractor.extract_json_from_html(test_html)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], {"special": 'quoted'})

    def test_nested_json(self):
        test_html = '''
        <script>
            {
                "outer": {
                    "inner": {
                        "value": 123
                    }
                }
            }
        </script>
        '''
        results = self.extractor.extract_json_from_html(test_html)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], {"outer": {"inner": {"value": 123}}})

    def test_save_json(self):
        test_obj = {"test": "save"}
        self.extractor.save_json(test_obj, "test.json")
        
        saved_path = os.path.join(self.test_dir, "extracted", "test.json")
        self.assertTrue(os.path.exists(saved_path))
        
        with open(saved_path, 'r', encoding='utf-8') as f:
            loaded = json.load(f)
        self.assertEqual(loaded, test_obj)

    def test_process_file(self):
        # Skapa en testfil
        test_content = '''
        <html>
            <script>
                {"test": "process"}
            </script>
        </html>
        '''
        test_file = os.path.join(self.test_dir, "test.html")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_content)

        results = self.extractor.process_file("test.html")
        self.assertIsNotNone(results)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], {"test": "process"})

    def test_multiple_json_objects(self):
        test_html = '''
        <script>
            {"first": 1}
            {"second": 2}
            {"third": 3}
        </script>
        '''
        results = self.extractor.extract_json_from_html(test_html)
        self.assertEqual(len(results), 3)
        self.assertEqual([obj for obj in results], [
            {"first": 1},
            {"second": 2},
            {"third": 3}
        ])

    def test_whitespace_handling(self):
        test_html = '''
        <script>
            {
                "test": "whitespace",
                "nested": {
                    "value": true
                }
            }
        </script>
        '''
        results = self.extractor.extract_json_from_html(test_html)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], {
            "test": "whitespace",
            "nested": {
                "value": True
            }
        })

    def test_json_arrays(self):
        test_html = '''
        <script>
            [
                {"item": 1},
                {"item": 2},
                {"item": 3}
            ]
        </script>
        '''
        results = self.extractor.extract_json_from_html(test_html)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], [
            {"item": 1},
            {"item": 2},
            {"item": 3}
        ])

if __name__ == '__main__':
    unittest.main()