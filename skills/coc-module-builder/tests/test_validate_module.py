"""Offline behavior tests. Synthetic pixels are not game art or AI outputs."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml
from PIL import Image, ImageDraw

SKILL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("module_validator", SKILL / "scripts/validate_module.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


class ModuleValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "module"
        shutil.copytree(SKILL / "tests/fixtures/quiet-lantern", self.root)

    def tearDown(self):
        self.temp.cleanup()

    def read(self, name):
        return yaml.safe_load((self.root / name).read_text())

    def write(self, name, data):
        (self.root / name).write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))

    def report(self, complete=False):
        return v.validate(self.root, complete)

    def actions(self):
        return {x["id"]: x["action"] for x in self.report()["resume"]}

    def assertError(self, fragment):
        result = self.report()
        self.assertFalse(result["ok"], result)
        self.assertTrue(any(fragment in e for e in result["errors"]), result)

    def stamp(self):
        result = self.report()
        plan = self.read("asset-plan.yaml")
        plan["content_fingerprint"] = result["content_fingerprint"]
        for item in result["resume"]:
            plan["items"][item["id"]]["input_fingerprint"] = item["input_fingerprint"]
        self.write("asset-plan.yaml", plan)

    def accept_all(self):
        style = self.read("visual-style.yaml")
        style.update(status="approved", approval_note="Fixture simulates explicit user selection; no AI art was generated.")
        self.write("visual-style.yaml", style)
        self.stamp()
        plan = self.read("asset-plan.yaml")
        index = self.read("assets/index.yaml")
        for aid, item in plan["items"].items():
            sprite = item["kind"] == "npc_sprite"
            image = Image.new("RGBA" if sprite else "RGB", item["size"], (0, 0, 0, 0) if sprite else (40, 30, 20))
            if sprite:
                ImageDraw.Draw(image).rectangle((200, 100, 800, 1400), fill=(160, 130, 100, 255))
            image.save(self.root / "assets" / item["output"])
            item["status"] = "accepted"
            item["attempts"] = [{"tool": "synthetic-test", "outcome": "accepted", "note": "Test pixels; not a real visual review."}]
            index["assets"][aid] = {
                "file": item["output"], "title": aid, "media_type": "image/png" if sprite else "image/webp",
                "kind": item["kind"], "source": {"kind": "generated"}, "sha256": v.digest((self.root / "assets" / item["output"]).read_bytes()),
                "relates_to": item["relates_to"], "tags": [], "access": {"default": "keeper_only", "player_reveal_fact": None},
                "visual_format_version": "0.1.0", "width": item["size"][0], "height": item["size"][1], "has_alpha": sprite,
                "generation": {"plan_id": aid, "style_version": item["style_version"], "content_fingerprint": plan["content_fingerprint"], "input_fingerprint": item["input_fingerprint"], "tool": "synthetic-test", "artistic_additions": "test rectangle", "review": {"status": "accepted", "note": "synthetic"}},
            }
            if sprite:
                index["assets"][aid]["anchor"] = [0.5, 1.0]
        self.write("asset-plan.yaml", plan)
        self.write("assets/index.yaml", index)
        return self.report(True)

    def test_draft_shared_and_fallback(self):
        result = self.report()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["progress"], {"planned": 5, "indexed": 0, "reusable": 0})
        loc = self.read("locations.yaml")["locations"]
        self.assertEqual(loc["hall"]["presentation"], loc["reading_room"]["presentation"])
        self.assertNotIn("presentation", loc["street"])
        self.assertEqual(self.actions()["shared_interior"], "generate")
        self.assertEqual(self.actions()["reading_room_detail"], "blocked")
        self.assertTrue(any("edition" in w for w in result["warnings"]))
        self.assertFalse(self.report(True)["ok"])

    def test_empty_template_is_parseable_draft(self):
        result = v.validate(SKILL / "assets/templates")
        self.assertTrue(result["ok"], result)

    def test_cover_reference_and_portrait_size(self):
        manifest = self.read("manifest.yaml")
        self.assertEqual(manifest["presentation"]["cover"], "module_cover")
        plan = self.read("asset-plan.yaml")
        plan["items"]["module_cover"]["size"] = [1920, 1080]
        self.write("asset-plan.yaml", plan)
        self.assertError("cover plan size")

    def test_cover_kind_and_real_format(self):
        manifest = self.read("manifest.yaml")
        manifest["presentation"]["cover"] = "shared_interior"
        self.write("manifest.yaml", manifest)
        self.assertError("wrong asset kind")
        manifest["presentation"]["cover"] = "module_cover"
        self.write("manifest.yaml", manifest)
        self.assertTrue(self.accept_all()["ok"])
        path = self.root / "assets/module_cover.webp"
        Image.new("RGBA", (1024, 1536), (20, 30, 40, 100)).save(path, format="PNG")
        index = self.read("assets/index.yaml")
        rec = index["assets"]["module_cover"]
        rec.update(sha256=v.digest(path.read_bytes()), media_type="image/png", has_alpha=True)
        self.write("assets/index.yaml", index)
        self.assertError("cover must be opaque")

    def test_accepted_resume_is_read_only_and_deterministic(self):
        result = self.accept_all()
        self.assertTrue(result["ok"], result)
        before = {p.relative_to(self.root).as_posix(): v.digest(p.read_bytes()) for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(self.report(), self.report())
        self.assertEqual(set(self.actions().values()), {"skip"})
        after = {p.relative_to(self.root).as_posix(): v.digest(p.read_bytes()) for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_duplicate_key(self):
        (self.root / "clues.yaml").write_text("clues: {}\nclues: {}\n")
        self.assertError("duplicate YAML key")

    def test_recursive_alias(self):
        (self.root / "clues.yaml").write_text("clues: &a\n  loop: *a\n")
        self.assertError("recursive")

    def test_malformed_collection(self):
        self.write("characters.yaml", {"characters": [], "instances": {}, "groups": {}})
        self.assertError("expected mapping")

    def test_source_text_changed(self):
        with (self.root / "story.md").open("a") as f:
            f.write("invented clue")
        self.assertError("source text changed")

    def test_duplicate_anchor(self):
        with (self.root / "story.md").open("a") as f:
            f.write('<a id="introduction"></a>\n')
        self.assertError("duplicate anchor")

    def test_unknown_anchor(self):
        data = self.read("characters.yaml")
        data["characters"]["archivist"]["source"]["anchor"] = "missing"
        self.write("characters.yaml", data)
        self.assertError("unknown reference 'missing'")

    def test_unknown_entity_and_presentation(self):
        data = self.read("locations.yaml")
        data["connections"][0]["to_location"] = "missing"
        data["locations"]["hall"]["presentation"]["background"] = "missing_bg"
        self.write("locations.yaml", data)
        self.assertError("unknown reference")

    def test_absolute_and_traversal_paths(self):
        for bad in ("/etc/passwd", "../outside.yaml", "C:/outside.yaml", "assets\\outside.yaml"):
            with self.subTest(bad=bad):
                data = self.read("manifest.yaml")
                data["files"]["clues"] = bad
                self.write("manifest.yaml", data)
                self.assertError("path")

    def test_symlink_escape(self):
        outside = Path(self.temp.name) / "outside.yaml"
        outside.write_text("clues: {}")
        (self.root / "clues.yaml").unlink()
        (self.root / "clues.yaml").symlink_to(outside)
        self.assertError("escapes")

    def test_missing_file_and_source_hash(self):
        data = self.read("manifest.yaml")
        data["source"]["text_sha256"] = "0" * 64
        self.write("manifest.yaml", data)
        self.assertError("hash mismatch")
        (self.root / "clues.yaml").unlink()
        self.assertError("missing file")

    def test_runtime_not_claimed(self):
        data = self.read("manifest.yaml")
        data["runtime_compatible"] = True
        self.write("manifest.yaml", data)
        self.assertError("runtime_compatible false")

    def test_no_image_tool_is_not_successful_generation(self):
        plan = self.read("asset-plan.yaml")
        plan["image_tool"] = "unavailable"
        for item in plan["items"].values():
            item["status"] = "blocked_tool"
        self.write("asset-plan.yaml", plan)
        self.assertTrue(self.report()["ok"])
        self.assertEqual(set(self.actions().values()), {"blocked"})
        self.assertFalse(self.report(True)["ok"])

    def test_partial_failure_and_retry_budget(self):
        plan = self.read("asset-plan.yaml")
        item = plan["items"]["shared_interior"]
        item["status"] = "failed"
        item["attempts"] = [{"tool": "stub", "outcome": "failed", "note": "offline failure"}]
        self.write("asset-plan.yaml", plan)
        self.assertEqual(self.actions()["shared_interior"], "generate")
        item["attempts"] *= 3
        self.write("asset-plan.yaml", plan)
        self.assertEqual(self.actions()["shared_interior"], "blocked")
        item["attempts"].append(copy.deepcopy(item["attempts"][0]))
        self.write("asset-plan.yaml", plan)
        self.assertError("budget exceeded")

    def test_style_version_and_prompt_changes_revise(self):
        self.assertTrue(self.accept_all()["ok"])
        style = self.read("visual-style.yaml")
        style["version"] = "0.2.0"
        self.write("visual-style.yaml", style)
        self.assertEqual(set(self.actions().values()), {"revise"})
        plan = self.read("asset-plan.yaml")
        plan["items"]["shared_interior"]["prompt"] += " a new camera angle"
        self.write("asset-plan.yaml", plan)
        self.assertEqual(self.actions()["shared_interior"], "revise")
        self.assertFalse(self.report(True)["ok"])

    def test_content_change_revises(self):
        self.accept_all()
        data = self.read("clues.yaml")
        data["clues"]["small_key"]["player_fact"] += "（已校对）"
        self.write("clues.yaml", data)
        self.assertEqual(set(self.actions().values()), {"revise"})

    def test_reference_bytes_change_revises(self):
        reference = self.root / "assets/reference.png"
        Image.new("RGB", (8, 8), "red").save(reference)
        plan = self.read("asset-plan.yaml")
        plan["items"]["shared_interior"]["references"] = ["assets/reference.png"]
        self.write("asset-plan.yaml", plan)
        self.assertTrue(self.accept_all()["ok"])
        Image.new("RGB", (8, 8), "blue").save(reference)
        self.assertEqual(self.actions()["shared_interior"], "revise")
        self.assertEqual(self.actions()["archivist_base"], "skip")

    def test_wrong_dimensions(self):
        self.accept_all()
        path = self.root / "assets/shared_interior.webp"
        Image.new("RGB", (320, 180), "black").save(path)
        index = self.read("assets/index.yaml")
        index["assets"]["shared_interior"]["sha256"] = v.digest(path.read_bytes())
        self.write("assets/index.yaml", index)
        self.assertError("size differs")

    def test_fake_transparency_and_empty_sprite(self):
        self.accept_all()
        path = self.root / "assets/archivist_base.png"
        for color in ((1, 1, 1, 255), (0, 0, 0, 0)):
            Image.new("RGBA", (1024, 1536), color).save(path)
            self.assertError("genuine transparency")

    def test_corrupt_image_and_changed_accepted_file(self):
        self.accept_all()
        (self.root / "assets/shared_interior.webp").write_bytes(b"not an image")
        self.assertError("cannot decode image")
        self.assertEqual(self.actions()["shared_interior"], "revise")

    def test_pending_not_allowed_in_index(self):
        self.accept_all()
        plan = self.read("asset-plan.yaml")
        plan["items"]["shared_interior"]["status"] = "review"
        self.write("asset-plan.yaml", plan)
        self.assertError("unaccepted plan must not be indexed")

    def test_accepted_requires_index(self):
        plan = self.read("asset-plan.yaml")
        plan["items"]["shared_interior"]["status"] = "accepted"
        self.write("asset-plan.yaml", plan)
        self.assertError("accepted plan missing indexed asset")

    def test_reuse_cycle(self):
        plan = self.read("asset-plan.yaml")
        plan["items"]["shared_interior"]["reuse_of"] = "shared_interior"
        self.write("asset-plan.yaml", plan)
        self.assertError("reuse cycle")

    def test_reuse_plan_without_extra_call(self):
        plan = self.read("asset-plan.yaml")
        item = copy.deepcopy(plan["items"]["shared_interior"])
        item["reuse_of"] = "shared_interior"
        plan["items"]["shared_copy"] = item
        self.write("asset-plan.yaml", plan)
        self.assertTrue(self.report()["ok"], self.report())
        self.assertEqual(self.actions()["shared_copy"], "reuse")

    def test_cli_works_outside_repo(self):
        result = subprocess.run([sys.executable, str(SKILL / "scripts/validate_module.py"), str(self.root), "--json"], cwd=self.temp.name, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["ok"])

    def test_bad_shape_is_diagnostic_not_traceback(self):
        self.write("asset-plan.yaml", {"visual_format_version": "0.1.0", "image_tool": "available", "items": {"broken": None}})
        self.assertError("expected mapping")

    def test_text_handout_is_not_binary_asset(self):
        index = self.read("assets/index.yaml")
        index["assets"]["note"] = {"title": "便条", "media_type": "text/markdown", "content_ref": {"document": "story.md", "anchor": "introduction"}, "source": {"document": "story.md", "anchor": "introduction"}, "relates_to": ["small_key"], "tags": ["展示材料"], "access": {"default": "keeper_only", "player_reveal_fact": "note_seen"}}
        self.write("assets/index.yaml", index)
        self.assertTrue(self.report()["ok"], self.report())

    def test_output_collision_without_reuse_is_rejected(self):
        plan = self.read("asset-plan.yaml")
        plan["items"]["duplicate"] = copy.deepcopy(plan["items"]["shared_interior"])
        self.write("asset-plan.yaml", plan)
        self.assertError("duplicate output")

    def test_later_batch_waits_for_user_style_choice(self):
        self.stamp()
        self.assertEqual(self.actions()["reading_room_detail"], "blocked")
        style = self.read("visual-style.yaml")
        style.update(status="approved", approval_note="Fixture user chooses style.")
        self.write("visual-style.yaml", style)
        self.stamp()
        self.assertEqual(self.actions()["reading_room_detail"], "generate")

    def test_sprite_cannot_be_background_or_fake_mime(self):
        self.accept_all()
        index = self.read("assets/index.yaml")
        index["assets"]["archivist_base"]["media_type"] = "application/octet-stream"
        self.write("assets/index.yaml", index)
        self.assertError("image media_type")

    def test_review_candidate_is_retained_without_regeneration(self):
        self.stamp()
        path = self.root / "assets/shared_interior.webp"
        Image.new("RGB", (1920, 1080), "black").save(path)
        plan = self.read("asset-plan.yaml")
        item = plan["items"]["shared_interior"]
        item.update(status="review", candidate_file="shared_interior.webp", sha256=v.digest(path.read_bytes()))
        item["attempts"] = [{"tool": "synthetic-test", "outcome": "review", "note": "Pending human review"}]
        self.write("asset-plan.yaml", plan)
        self.assertTrue(self.report()["ok"], self.report())
        self.assertEqual(self.actions()["shared_interior"], "review")

    def test_parent_cycle_and_missing_source_anchor(self):
        loc = self.read("locations.yaml")
        loc["locations"]["hall"]["parent"] = "reading_room"
        loc["locations"]["reading_room"]["parent"] = "hall"
        loc["locations"]["hall"]["source"].pop("anchor")
        self.write("locations.yaml", loc)
        self.assertError("parent cycle")
        self.assertError("source requires document and anchor")


if __name__ == "__main__":
    unittest.main()
