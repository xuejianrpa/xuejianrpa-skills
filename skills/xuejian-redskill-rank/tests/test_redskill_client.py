"""Unit tests for redskill_client data shaping (no network required)."""

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "redskill_client.py"
SPEC = importlib.util.spec_from_file_location("redskill_client", SCRIPT_PATH)
CLIENT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CLIENT
SPEC.loader.exec_module(CLIENT)


FIXTURE = {
    "dataDate": "2026-08-19",
    "genTime": "2026-08-20 09:58:40",
    "useList": [
        {"skill_id": 1519, "skill_name": "alpha", "skill_description": "top skill", "use_cnt": 100, "use_users": 50, "note_id": "note-a"},
        {"skill_id": 200, "skill_name": "beta-xhs", "skill_description": "xhs helper", "use_cnt": 80, "use_users": 40, "note_id": "note-b"},
    ],
    "newList": [
        {"skill_id": 200, "skill_name": "beta-xhs", "skill_description": "xhs helper", "new7_cnt": 9, "cum_cnt": 80, "note_id": "note-b"},
    ],
    "todayList": [
        {"skill_id": 999, "skill_name": "fresh", "skill_description": "new today", "use_cnt": 3, "use_users": 2, "note_id": None},
    ],
    "authorList": [
        {"author_id": "auth1", "skill_cnt": 12, "nickname": "someone"},
    ],
    "allSkills": [
        {"skill_id": "1519", "skill_name": "alpha", "skill_description": "top skill"},
        {"skill_id": "300", "skill_name": "gamma-only-all", "skill_description": "only in allSkills"},
    ],
}


class ShapeSummaryTests(unittest.TestCase):
    def test_summary_counts_and_dates(self):
        summary = CLIENT.shape_summary(FIXTURE)
        self.assertTrue(summary["ok"])
        self.assertEqual(summary["dataDate"], "2026-08-19")
        self.assertEqual(summary["counts"]["useList"], 2)
        self.assertEqual(summary["counts"]["newList"], 1)
        self.assertEqual(summary["counts"]["todayList"], 1)
        self.assertEqual(summary["counts"]["authorList"], 1)
        self.assertEqual(summary["counts"]["allSkills"], 2)


class ShapeTopTests(unittest.TestCase):
    def test_top_generates_rank_by_index(self):
        rows = CLIENT.shape_top_rows(FIXTURE, "use")
        self.assertEqual([r["rank"] for r in rows], [1, 2])
        self.assertEqual(rows[0]["skill_name"], "alpha")

    def test_top_alias_and_canonical(self):
        for alias in ("use", "users", "useList"):
            self.assertEqual(len(CLIENT.shape_top_rows(FIXTURE, alias)), 2)
        self.assertEqual(len(CLIENT.shape_top_rows(FIXTURE, "allSkills")), 2)
        self.assertEqual(len(CLIENT.shape_top_rows(FIXTURE, "authorList")), 1)

    def test_top_unknown_list_raises(self):
        with self.assertRaises(SystemExit):
            CLIENT.shape_top_rows(FIXTURE, "nonexistent")


class ShapeSearchTests(unittest.TestCase):
    def test_search_matches_name_case_insensitive(self):
        rows = CLIENT.shape_search_rows(FIXTURE, "XHS", 10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["skill_id"], 200)

    def test_search_matches_description(self):
        rows = CLIENT.shape_search_rows(FIXTURE, "only in allSkills", 10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "allSkills")

    def test_search_dedupes_across_lists(self):
        # skill 200 appears in useList and newList -> only once, with merged fields
        rows = CLIENT.shape_search_rows(FIXTURE, "beta", 10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["use_users"], 40)
        self.assertEqual(rows[0]["new7_cnt"], 9)

    def test_search_respects_limit(self):
        rows = CLIENT.shape_search_rows(FIXTURE, "skill", 1)
        self.assertLessEqual(len(rows), 1)


class ShapeDetailTests(unittest.TestCase):
    def test_detail_by_skill_id_from_ranked_list(self):
        rows = CLIENT.shape_detail_rows(FIXTURE, "1519", None)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["skill_name"], "alpha")
        self.assertEqual(rows[0]["source"], "useList")

    def test_detail_by_skill_id_number_vs_string_normalized(self):
        # useList stores number 1519, allSkills stores string "1519"
        rows = CLIENT.shape_detail_rows(FIXTURE, "1519", None)
        self.assertEqual(rows[0]["skill_id"], 1519)
        # a skill only present in allSkills still resolves via string id
        rows = CLIENT.shape_detail_rows(FIXTURE, "300", None)
        self.assertEqual(rows[0]["skill_name"], "gamma-only-all")
        self.assertEqual(rows[0]["source"], "allSkills")

    def test_detail_by_note_id(self):
        rows = CLIENT.shape_detail_rows(FIXTURE, None, "note-b")
        self.assertEqual(rows[0]["skill_id"], 200)

    def test_detail_not_found_returns_empty(self):
        self.assertEqual(CLIENT.shape_detail_rows(FIXTURE, "404404", None), [])
        self.assertEqual(CLIENT.shape_detail_rows(FIXTURE, None, "no-such-note"), [])


class CacheKeyTests(unittest.TestCase):
    def test_cache_key_ignores_refresh_param(self):
        a = CLIENT.cache_key("https://example/data.json", {"refresh": "true"})
        b = CLIENT.cache_key("https://example/data.json", None)
        self.assertEqual(a, b)

    def test_cache_key_differs_by_endpoint(self):
        a = CLIENT.cache_key("https://a/data.json", None)
        b = CLIENT.cache_key("https://b/data.json", None)
        self.assertNotEqual(a, b)


class EndpointTests(unittest.TestCase):
    def test_default_endpoint_is_https_json(self):
        endpoint = CLIENT.default_endpoint()
        self.assertTrue(endpoint.startswith("https://"))
        self.assertTrue(endpoint.endswith(".json"))


if __name__ == "__main__":
    unittest.main()
