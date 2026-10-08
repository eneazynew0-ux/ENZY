import unittest
import importlib
import sys
import types
from unittest.mock import patch

from engine.factual_identity_gate import check_factual_identity
from engine.multi_provider_search import search_wikimedia
from engine.media_downloader import _clean_media_url
from engine.multi_query_search import search_queries_raw
from engine.multi_query_visual_pipeline import run_multi_query_visual_pipeline


ENTITY = {
    "canonical_subject": "Zimbabwe Bird",
    "subject_type": "soapstone sculpture",
    "location": "Great Zimbabwe",
    "aliases_or_descriptions": ["carved soapstone bird"],
    "_identity_scope": "ARTIFACT_GROUP",
}


def asset(title, description, license_short, mime="image/jpeg"):
    return {
        "provider": "wikimedia",
        "pageid": title,
        "title": title,
        "description": description,
        "mime": mime,
        "width": 1200,
        "height": 1800,
        "license_short": license_short,
        "license_url": "https://example.test/license",
        "description_url": "https://commons.wikimedia.org/wiki/" + title,
        "preview_url": "https://upload.wikimedia.org/" + title,
    }


class ZimbabweBirdIdentityTraceTest(unittest.TestCase):
    def test_reported_false_claim_is_not_visualized_as_fact(self):
        fake_mlx_lm = types.ModuleType("mlx_lm")
        fake_mlx_lm.generate = lambda *_args, **_kwargs: None
        with patch.dict(sys.modules, {"mlx_lm": fake_mlx_lm}):
            semantic_gate = importlib.import_module("engine.beat_semantic_gate")

        beat = {
            "voice_text": (
                "Африка южнее Сахары не знала ни городов, ни инженерии, "
                "ни письменной культуры."
            ),
            "visual_intent": "A factual blank map of Africa with no cities.",
            "search_queries": ["empty map Africa no cities no engineering"],
            "requirements": ["no written culture", "absence of development"],
            "avoid": [],
            "edit": "Emphasize the absence of human development.",
        }

        issues = semantic_gate.check_beat_semantics(
            beat,
            {"withheld_entities": [], "entities": []},
            "Учебник скажет вам: до прихода европейцев",
            model=None,
            tokenizer=None,
        )

        self.assertEqual(len(issues), 1)
        self.assertEqual(
            issues[0]["type"],
            "REPORTED_CLAIM_VISUALIZED_AS_FACT",
        )

    def test_visual_description_instruction_echo_is_rejected(self):
        fake_mlx_lm = types.ModuleType("mlx_lm")
        fake_mlx_lm.load = lambda *_args, **_kwargs: None
        fake_mlx_lm.generate = lambda *_args, **_kwargs: None

        with patch.dict(sys.modules, {"mlx_lm": fake_mlx_lm}):
            judge = importlib.import_module("engine.visual_judge")

        self.assertFalse(
            judge._description_is_valid(
                "Answer with a short factual description. The subject is a gray rock."
            )
        )
        self.assertTrue(
            judge._description_is_valid(
                "A dark stone tablet has several dense horizontal lines of carved writing."
            )
        )

    def test_wikimedia_tracking_parameters_are_removed(self):
        url = (
            "https://upload.wikimedia.org/file.jpg?"
            "utm_source=commons.wikimedia.org&width=800&utm_campaign=test"
        )
        self.assertEqual(
            _clean_media_url(url),
            "https://upload.wikimedia.org/file.jpg?width=800",
        )

    def test_artifact_and_symbol_are_distinguished(self):
        original = asset(
            "File:Zimbabwebird1.jpg",
            "Zimbabwe Bird carved soapstone sculpture from Great Zimbabwe",
            "CC BY 2.5",
        )
        symbol = asset(
            "File:Zimbabwe Bird.svg",
            "Zimbabwe Bird national emblem vector illustration",
            "Public domain",
            mime="image/svg+xml",
        )

        self.assertEqual(
            check_factual_identity(original, ENTITY)["identity_label"],
            "ORIGINAL_ARTIFACT",
        )
        symbol_decision = check_factual_identity(symbol, ENTITY)
        self.assertEqual(symbol_decision["status"], "UNVERIFIED")
        self.assertEqual(symbol_decision["identity_label"], "SYMBOL")

    def test_replica_marker_overrides_commons_category(self):
        replica = asset(
            "File:Zimbabwebird1.jpg",
            "Zimbabwe bird bannister",
            "CC BY 2.5",
        )
        replica["source_metadata"] = {
            "Categories": {"value": "Great Zimbabwe|Zimbabwe Bird"}
        }

        decision = check_factual_identity(replica, ENTITY)
        self.assertEqual(decision["status"], "UNVERIFIED")
        self.assertEqual(decision["identity_label"], "REPLICA")

    def test_historical_artifact_is_verified_from_commons_metadata(self):
        historical = asset(
            "File:Soapstone birds on pedestals.jpg",
            "Historic photograph of soapstone birds on pedestals",
            "Public domain",
        )
        historical["source_metadata"] = {
            "Categories": {
                "value": "Zimbabwe Bird|Art made from steatite|PD-old-70-expired"
            }
        }

        decision = check_factual_identity(historical, ENTITY)
        self.assertEqual(decision["status"], "VERIFIED")
        self.assertEqual(decision["identity_label"], "ORIGINAL_ARTIFACT")

    def test_symbol_categories_do_not_become_artifacts(self):
        cases = [
            ("File:Revenue stamps.jpg", "Revenue stamps of Zimbabwe"),
            ("File:Building detail.jpg", "Historical coats of arms of Zimbabwe"),
            ("File:Rodezya Arması.png", "Birds in crest"),
        ]

        for title, categories in cases:
            with self.subTest(title=title):
                symbol = asset(title, "Zimbabwe Bird", "Public domain")
                symbol["source_metadata"] = {
                    "Categories": {"value": f"Zimbabwe Bird|{categories}"}
                }
                decision = check_factual_identity(symbol, ENTITY)
                self.assertEqual(decision["status"], "UNVERIFIED")
                self.assertEqual(decision["identity_label"], "SYMBOL")

    @patch("engine.multi_provider_search.search_commons")
    def test_zimbabwe_search_uses_bitmap_category(self, search_commons):
        search_commons.return_value = []

        search_wikimedia("Zimbabwe Bird", limit=10)

        search_commons.assert_called_once_with(
            'incategory:"Zimbabwe Bird" filetype:bitmap',
            limit=20,
        )

    @patch("engine.multi_query_search.search_pexels_photos", return_value=[])
    @patch("engine.multi_query_search.search_pixabay_photos", return_value=[])
    @patch("engine.multi_query_search.search_internet_archive", return_value=[])
    @patch("engine.multi_query_search.search_wikimedia")
    def test_factual_entity_adds_one_commons_category_search(
        self,
        search_wikimedia_mock,
        _archive,
        _pixabay,
        _pexels,
    ):
        search_wikimedia_mock.return_value = []

        result = search_queries_raw(
            ["Rosetta Stone artifact photograph"],
            limit_per_provider=10,
            wikimedia_category="Rosetta Stone",
        )

        calls = search_wikimedia_mock.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(
            calls[1].args[0],
            'incategory:"Rosetta Stone" filetype:bitmap',
        )
        self.assertEqual(calls[1].kwargs["limit"], 20)
        self.assertIn("Commons category: Rosetta Stone", result["query_stats"])

    @patch("engine.multi_query_visual_pipeline.search_queries_raw")
    def test_correct_but_attribution_required_asset_is_traced(self, search):
        original = asset(
            "File:Zimbabwebird1.jpg",
            "Zimbabwe Bird carved soapstone sculpture from Great Zimbabwe",
            "CC BY 2.5",
        )
        symbol = asset(
            "File:Zimbabwe Bird.svg",
            "Zimbabwe Bird national emblem vector illustration",
            "Public domain",
            mime="image/svg+xml",
        )
        search.return_value = {
            "queries": ["Zimbabwe Bird"],
            "provider_stats": {"wikimedia": 2},
            "query_stats": {},
            "stats": {
                "search_found_raw": 2,
                "search_unique": 2,
                "rights_allowed": 2,
                "rights_rejected": 0,
            },
            "assets": [original, symbol],
            "rights_rejected": [],
        }

        result = run_multi_query_visual_pipeline(
            ["Zimbabwe Bird"],
            "actual Zimbabwe Bird artifact",
            factual=True,
            visual_entity=ENTITY,
        )

        self.assertIsNone(result["best"])
        self.assertEqual(result["stats"]["identity_verified"], 1)
        self.assertEqual(result["stats"]["identity_rejected"], 1)
        self.assertEqual(result["stats"]["export_rights_rejected"], 1)
        self.assertEqual(
            result["export_rights_rejected"][0]["factual_identity"]["identity_label"],
            "ORIGINAL_ARTIFACT",
        )
        self.assertEqual(
            result["identity_rejected"][0]["factual_identity"]["identity_label"],
            "SYMBOL",
        )


if __name__ == "__main__":
    unittest.main()
