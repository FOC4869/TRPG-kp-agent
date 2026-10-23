# /// script
# requires-python = ">=3.12"
# dependencies = ["PyYAML==6.0.3", "Pillow==12.0.0"]
# ///
"""Read-only CoC authored-content/visual production validator. No game runtime."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import unittest

try:
    import yaml
    from PIL import Image
except ImportError:
    print("Missing PyYAML/Pillow: use uv run --locked --script validate_module.py MODULE_DIR", file=sys.stderr)
    sys.exit(2)

CORE = {
    "characters": ("characters", "instances", "groups"),
    "locations": ("locations", "map_features"),
    "clues": ("clues",), "objects": ("objects",), "events": ("events",),
    "endings": ("rewards",), "keeper_options": ("options",), "issues": ("issues",),
}
FILES = ("story", *CORE, "assets", "visual_style", "asset_plan")
KINDS = {"module_cover", "default_background", "scene_background", "npc_sprite", "creature_sprite"}
STATES = {"planned", "blocked_tool", "review", "accepted", "failed"}
ANCHOR = re.compile(r'^<a id="([a-z][a-z0-9_-]*)"></a>\n?', re.MULTILINE)
ID = re.compile(r"^[a-z][a-z0-9_]*$")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise ValueError("YAML mapping keys must be strings")
        if key in result:
            raise ValueError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def walk(value, trail="", stack=None):
    stack = set() if stack is None else stack
    if not isinstance(value, (dict, list)):
        return
    if id(value) in stack:
        raise ValueError(f"recursive YAML alias at {trail}")
    stack.add(id(value))
    yield trail, value
    iterator = value.items() if isinstance(value, dict) else enumerate(value)
    for key, child in iterator:
        yield from walk(child, f"{trail}.{key}" if trail else str(key), stack)
    stack.remove(id(value))


def without_presentation(value):
    if isinstance(value, dict):
        return {k: without_presentation(v) for k, v in value.items() if k != "presentation"}
    if isinstance(value, list):
        return [without_presentation(v) for v in value]
    return value


class Validator:
    def __init__(self, root: Path, complete=False):
        self.root = root.resolve()
        self.complete = complete
        self.errors = []
        self.warnings = []
        self.docs = {}
        self.paths = {}
        self.tables = {}
        self.entities = set()
        self.anchors = {}
        self.assets = {}
        self.items = {}
        self.fingerprint = ""
        self.resume = []

    def error(self, where, message):
        self.errors.append(f"{where}: {message}")

    def mapping(self, value, where):
        if not isinstance(value, dict):
            self.error(where, "expected mapping")
            return {}
        return value

    def sequence(self, value, where):
        if not isinstance(value, list):
            self.error(where, "expected list")
            return []
        return value

    def path(self, value, where, base=None):
        if not isinstance(value, str) or not value or "\\" in value:
            self.error(where, "expected nonempty POSIX relative path")
            return None
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or ":" in value:
            self.error(where, "path escapes or is absolute")
            return None
        boundary = (base or self.root).resolve()
        result = (boundary / value).resolve()
        if not result.is_relative_to(boundary) or not result.is_relative_to(self.root):
            self.error(where, "symlink/path escapes allowed root")
            return None
        if not result.is_file():
            self.error(where, f"missing file {value}")
            return None
        return result

    def load(self, path):
        try:
            obj = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueLoader)
            list(walk(obj))
            return self.mapping(obj, str(path.relative_to(self.root)))
        except (ValueError, OSError, UnicodeError, yaml.YAMLError) as exc:
            self.error(str(path.relative_to(self.root)), str(exc))
            return {}

    def ref(self, value, allowed, where, nullable=False):
        if value is None and nullable:
            return
        if not isinstance(value, str) or value not in allowed:
            self.error(where, f"unknown reference {value!r}")

    def source(self, value, where):
        src = self.mapping(value, where)
        if "document" not in src:
            if src.get("kind") != "generated":
                self.error(where, "expected document/anchor or generated provenance")
            return
        path = self.path(src.get("document"), where)
        anchor = src.get("anchor")
        if path and anchor is not None:
            if path not in self.anchors:
                text = path.read_text(encoding="utf-8")
                self.anchors[path] = ANCHOR.findall(text.replace("\r\n", "\n").replace("\r", "\n"))
            self.ref(anchor, self.anchors[path], where + ".anchor")

    def prepare(self):
        if not self.root.is_dir():
            self.error("module", "not a directory")
            return
        manifest = self.path("manifest.yaml", "manifest")
        self.docs["manifest"] = self.load(manifest) if manifest else {}
        m = self.docs["manifest"]
        files = self.mapping(m.get("files"), "manifest.files")
        for key in FILES:
            path = self.path(files.get(key), f"manifest.files.{key}")
            if path:
                self.paths[key] = path
                if key != "story":
                    self.docs[key] = self.load(path)
        # Reject broken/duplicate YAML even in author-defined extra files.
        known = set(self.paths.values()) | ({manifest} if manifest else set())
        for path in sorted(self.root.rglob("*")):
            if path.suffix.lower() in {".yaml", ".yml"} and path not in known:
                checked = self.path(path.relative_to(self.root).as_posix(), "extra YAML")
                if checked:
                    self.load(checked)
        for key, collections in CORE.items():
            for name in collections:
                table = self.mapping(self.docs.get(key, {}).get(name), f"{key}.{name}")
                self.tables[name] = table
                if name in {"issues", "rewards", "options", "map_features"}:
                    continue
                for entity, record in table.items():
                    if not ID.fullmatch(entity):
                        self.error(name, f"invalid ID {entity}")
                    if entity in self.entities:
                        self.error(name, f"duplicate entity ID {entity}")
                    self.entities.add(entity)
                    self.mapping(record, f"{name}.{entity}")
        self.assets = self.mapping(self.docs.get("assets", {}).get("assets"), "assets.assets")
        self.items = self.mapping(self.docs.get("asset_plan", {}).get("items"), "asset_plan.items")

    def content(self):
        m = self.docs.get("manifest", {})
        for name in ("id", "title", "content_version", "language"):
            if not isinstance(m.get(name), str) or not m[name].strip():
                self.error("manifest", f"missing string {name}")
        if not isinstance(m.get("id"), str) or not ID.fullmatch(m["id"]):
            self.error("manifest.id", "expected snake_case ID")
        if m.get("schema_version") != "0.1.0" or m.get("status") != "authored_draft" or m.get("runtime_compatible") is not False:
            self.error("manifest", "expected schema 0.1.0, authored_draft, runtime_compatible false")
        access = self.mapping(m.get("access"), "manifest.access")
        if access.get("default") != "keeper_only" or access.get("static_publication") is not False:
            self.error("manifest.access", "must default deny and forbid static publication")
        rules = self.mapping(m.get("rules"), "manifest.rules")
        if rules.get("system") != "Call of Cthulhu":
            self.error("manifest.rules", "expected Call of Cthulhu")
        if rules.get("edition") is None:
            self.ref(rules.get("issue"), self.tables.get("issues", {}), "manifest.rules.issue")
            self.warnings.append("Rules edition unresolved; runtime remains unavailable")
        entry = self.mapping(m.get("entry"), "manifest.entry")
        self.ref(entry.get("location"), self.tables.get("locations", {}), "entry.location", True)
        self.ref(entry.get("event"), self.tables.get("events", {}), "entry.event", True)
        if self.docs.get("events", {}).get("execution") != "descriptive_only":
            self.error("events.execution", "must be descriptive_only")
        source = self.mapping(m.get("source"), "manifest.source")
        original = self.path(source.get("document"), "manifest.source.document")
        story_path = self.paths.get("story")
        story = story_path.read_text(encoding="utf-8") if story_path else ""
        anchors = ANCHOR.findall(story)
        if len(anchors) != len(set(anchors)):
            self.error("story", "duplicate anchor IDs")
        if story_path:
            self.anchors[story_path] = anchors
        original_hash = ""
        if original:
            original_hash = digest(original.read_bytes())
            if source.get("text_sha256") != original_hash:
                self.error("manifest.source.text_sha256", "hash mismatch")
            raw = original.read_bytes().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
            if ANCHOR.sub("", story) != raw:
                self.error("story", "source text changed beyond newline normalization/inserted anchors")
        core_manifest = {k: v for k, v in m.items() if k not in {"files", "presentation"}}
        core_docs = {k: without_presentation(self.docs.get(k, {})) for k in CORE}
        self.fingerprint = digest(canonical({"manifest": core_manifest, "documents": core_docs, "story": story, "original_sha256": original_hash}))
        for name in ("characters", "instances", "groups", "locations", "clues", "objects", "events", "options", "issues", "rewards"):
            for entity, value in self.tables.get(name, {}).items():
                rec = self.mapping(value, f"{name}.{entity}")
                if "source" not in rec and not rec.get("sources"):
                    self.error(f"{name}.{entity}", "missing source")
                if name in {"characters", "locations", "clues", "objects"} and not rec.get("name"):
                    self.error(f"{name}.{entity}", "missing name")
                if name == "characters" and rec.get("kind") not in {"npc", "creature_template"}:
                    self.error(f"{name}.{entity}", "invalid character kind")
                for source_rec in ([rec["source"]] if "source" in rec else rec.get("sources", [])):
                    if not isinstance(source_rec, dict) or not source_rec.get("document") or not source_rec.get("anchor"):
                        self.error(f"{name}.{entity}", "entity source requires document and anchor")
                if name == "events" and not rec.get("trigger"):
                    self.error(f"{name}.{entity}", "missing trigger")
                if name in {"instances", "groups"}:
                    template = self.tables.get("characters", {}).get(rec.get("template"))
                    if not isinstance(template, dict) or template.get("kind") != "creature_template":
                        self.error(f"{name}.{entity}", "template must reference creature_template")
                if name == "options" and rec.get("enabled") is not False:
                    self.error(f"options.{entity}", "authored optional choices must default false")
                if name == "issues" and rec.get("status") == "open":
                    self.warnings.append(f"Open issue: {entity}")
        conns = self.sequence(self.docs.get("locations", {}).get("connections"), "locations.connections")
        connection_ids = set()
        for conn in conns:
            conn = self.mapping(conn, "connection")
            cid = conn.get("id")
            if not isinstance(cid, str) or not ID.fullmatch(cid) or cid in connection_ids:
                self.error("connections", "missing/duplicate/invalid connection ID")
            else:
                connection_ids.add(cid)
            if type(conn.get("bidirectional")) is not bool:
                self.error("connections", "bidirectional must be boolean")
            if "source" not in conn:
                self.error("connections", "missing source")
        locations = self.tables.get("locations", {})
        for lid, value in locations.items():
            seen = {lid}
            current = value
            while isinstance(current, dict) and current.get("parent") in locations:
                parent = current["parent"]
                if parent in seen:
                    self.error("locations", f"parent cycle at {lid}")
                    break
                seen.add(parent)
                current = locations[parent]

    def references(self):
        allowed_assets = set(self.assets) | set(self.items)
        singular = {"location": "locations", "from_location": "locations", "to_location": "locations", "parent": "locations", "template": "characters", "npc": "characters", "clue": "clues", "object": "objects", "via_object": "objects", "issue": "issues", "optional_relocation": "options"}
        for file, doc in self.docs.items():
            for trail, value in walk(doc, file):
                if not isinstance(value, dict):
                    continue
                for key, child in value.items():
                    where = trail + "." + key
                    if key in {"source", "content_ref"} and isinstance(child, dict) and ("document" in child or file != "manifest"):
                        self.source(child, where)
                    elif key == "sources":
                        for src in self.sequence(child, where):
                            self.source(src, where)
                    elif key in singular and child is not None and file not in {"visual_style", "asset_plan"}:
                        self.ref(child, self.tables.get(singular[key], {}), where)
                    elif key == "target" and child is not None:
                        self.ref(child, self.entities, where)
                    elif key in {"asset", "detail_map"}:
                        self.ref(child, self.assets, where)
                    elif key in {"relates_to", "locations", "clues"} and isinstance(child, list):
                        allowed = self.entities if key == "relates_to" else self.tables.get(key, {})
                        for item in child:
                            self.ref(item, allowed, where)
                    elif key == "presentation":
                        pres = self.mapping(child, where)
                        for bg in ("background", "default_background", "cover"):
                            if bg in pres:
                                self.ref(pres[bg], allowed_assets, where + "." + bg)
                                definition = self.items.get(pres[bg], self.assets.get(pres[bg], {})) if isinstance(pres[bg], str) else {}
                                expected = {"module_cover"} if bg == "cover" else {"default_background"} if bg == "default_background" else {"scene_background", "default_background"}
                                if isinstance(definition, dict) and definition.get("kind") not in expected:
                                    self.error(where, "background references wrong asset kind")
                        if "sprites" in pres:
                            for sprite in self.mapping(pres["sprites"], where + ".sprites").values():
                                self.ref(sprite, allowed_assets, where + ".sprites")
                                rec = self.items.get(sprite, self.assets.get(sprite, {})) if isinstance(sprite, str) else {}
                                if isinstance(rec, dict) and rec.get("kind") not in {"npc_sprite", "creature_sprite"}:
                                    self.error(where, "sprite references wrong asset kind")

    def image(self, path, rec, where):
        try:
            with Image.open(path) as im:
                im.load()
                width, height = im.size
                has_alpha = "A" in im.getbands() or "transparency" in im.info
                expected_mime = Image.MIME.get(im.format)
                if expected_mime != rec.get("media_type"):
                    self.error(where, "media_type does not match decoded image")
                for field, actual in (("width", width), ("height", height), ("has_alpha", has_alpha)):
                    if field in rec and (type(rec[field]) is not type(actual) or rec[field] != actual):
                        self.error(where, f"{field} metadata mismatch")
                if rec.get("kind") in {"npc_sprite", "creature_sprite"}:
                    alpha = im.convert("RGBA").getchannel("A").getextrema()
                    if not has_alpha or alpha[0] != 0 or alpha[1] == 0:
                        self.error(where, "sprite needs genuine transparency and visible subject pixels")
                return [width, height], has_alpha, im.format
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            self.error(where, f"cannot decode image: {exc}")
            return None

    def asset_files(self):
        doc = self.docs.get("assets", {})
        if doc.get("format_version") != "0.1.0" or doc.get("path_base") != "assets/":
            self.error("assets", "expected format_version 0.1.0 and path_base assets/")
        for aid, value in self.assets.items():
            where = f"assets.{aid}"
            rec = self.mapping(value, where)
            self.mapping(rec.get("source"), where + ".source")
            for field in ("title", "media_type"):
                if not isinstance(rec.get(field), str) or not rec[field]:
                    self.error(where, f"missing {field}")
            self.sequence(rec.get("relates_to"), where + ".relates_to")
            self.sequence(rec.get("tags"), where + ".tags")
            access = self.mapping(rec.get("access"), where + ".access")
            if access.get("default") != "keeper_only":
                self.error(where, "asset must default keeper_only")
            fact = access.get("player_reveal_fact")
            if fact is not None and (not isinstance(fact, str) or not ID.fullmatch(fact)):
                self.error(where, "invalid reveal fact ID")
            if ("file" in rec) == ("content_ref" in rec):
                self.error(where, "expected exactly one of file/content_ref")
            if "file" not in rec:
                continue
            if "generation" in rec and not str(rec.get("media_type", "")).startswith("image/"):
                self.error(where, "generated visual asset requires image media_type")
            path = self.path(rec["file"], where, self.root / "assets")
            if path and rec.get("sha256") != digest(path.read_bytes()):
                self.error(where, "file hash mismatch")
            if path and isinstance(rec.get("media_type"), str) and rec["media_type"].startswith("image/"):
                info = self.image(path, rec, where)
                if "generation" in rec and info:
                    for required in ("width", "height", "has_alpha", "visual_format_version"):
                        if required not in rec:
                            self.error(where, f"generated asset missing {required}")
                    if rec.get("visual_format_version") != "0.1.0":
                        self.error(where, "unsupported visual asset version")
                    plan = self.items.get(aid)
                    if isinstance(plan, dict):
                        if info[0] != plan.get("size"):
                            self.error(where, "decoded image size differs from plan")
                        if rec.get("kind") != plan.get("kind"):
                            self.error(where, "kind differs from plan")
                    if rec.get("kind") in {"scene_background", "default_background"} and (info[0] != [1920, 1080] or info[1] or info[2] != "WEBP"):
                        self.error(where, "background must be opaque 1920x1080 WebP")
                    if rec.get("kind") == "module_cover" and (info[0] != [1024, 1536] or info[1] or info[2] != "WEBP"):
                        self.error(where, "cover must be opaque 1024x1536 WebP")
                    if rec.get("kind") in {"npc_sprite", "creature_sprite"} and info[2] != "PNG":
                        self.error(where, "sprite must be PNG")
            if rec.get("kind") in {"npc_sprite", "creature_sprite"}:
                anchor = rec.get("anchor")
                if not isinstance(anchor, list) or len(anchor) != 2 or not all(type(x) in (int, float) and 0 <= x <= 1 for x in anchor):
                    self.error(where, "sprite anchor must be two normalized coordinates")
            if "generation" in rec:
                self.ref(aid, self.items, where + ".generation.plan_id")
                self.mapping(rec["generation"], where + ".generation")

    def production(self):
        style = self.docs.get("visual_style", {})
        plan_doc = self.docs.get("asset_plan", {})
        for key, doc in (("visual_style", style), ("asset_plan", plan_doc)):
            if doc.get("visual_format_version") != "0.1.0":
                self.error(key, "expected visual_format_version 0.1.0")
        if style.get("status") not in {"draft", "approved"}:
            self.error("visual_style", "invalid status")
        if style.get("status") == "approved" and not style.get("approval_note"):
            self.error("visual_style", "approved style needs actual user selection record")
        if self.complete and self.items and style.get("status") != "approved":
            self.error("visual_style", "complete production requires user-selected approved style")
        if not isinstance(style.get("version"), str) or not style["version"]:
            self.error("visual_style", "missing version")
        for ref in self.sequence(style.get("references"), "visual_style.references"):
            self.path(ref, "visual_style.references")
        available = plan_doc.get("image_tool") == "available"
        if plan_doc.get("image_tool") not in {"available", "unavailable"}:
            self.error("asset_plan.image_tool", "expected available/unavailable")
        if plan_doc.get("content_fingerprint") != self.fingerprint:
            self.warnings.append("asset_plan.content_fingerprint differs from current content; refresh before production")
        style_path = self.paths.get("visual_style")
        style_hash = digest(style_path.read_bytes()) if style_path else ""
        if self.items and not self.docs.get("manifest", {}).get("presentation", {}).get("default_background"):
            self.error("manifest.presentation", "nonempty visual plan requires default_background")
        for aid, value in sorted(self.items.items()):
            where = "asset_plan.items." + aid
            rec = self.mapping(value, where)
            start_errors = len(self.errors)
            if not ID.fullmatch(aid):
                self.error(where, "invalid plan ID")
            if rec.get("kind") not in KINDS:
                self.error(where, "invalid generated kind")
            if rec.get("status") not in STATES or rec.get("batch") not in {"sample", "later"}:
                self.error(where, "invalid state/batch")
            if not isinstance(rec.get("prompt"), str) or not rec["prompt"].strip():
                self.error(where, "missing final prompt")
            relates = self.sequence(rec.get("relates_to"), where + ".relates_to")
            refs = []
            for ref in self.sequence(rec.get("references"), where + ".references"):
                path = self.path(ref, where + ".references")
                refs.append({"file": ref, "sha256": digest(path.read_bytes()) if path else None})
            output = rec.get("output")
            if not isinstance(output, str) or not output or PurePosixPath(output).is_absolute() or ".." in PurePosixPath(output).parts or "\\" in output or ":" in output:
                self.error(where, "invalid output relative path")
            elif not (self.root / "assets").resolve().is_relative_to(self.root) or not (self.root / "assets" / output).resolve().is_relative_to((self.root / "assets").resolve()):
                self.error(where, "output escapes assets")
            size = rec.get("size")
            valid_size = isinstance(size, list) and len(size) == 2 and all(type(n) is int and n > 0 for n in size)
            if not valid_size:
                self.error(where, "size must be two positive integers")
            elif rec.get("kind") in {"scene_background", "default_background"} and size != [1920, 1080]:
                self.error(where, "background plan size must be 1920x1080")
            elif rec.get("kind") == "module_cover" and size != [1024, 1536]:
                self.error(where, "cover plan size must be 1024x1536")
            elif rec.get("kind") == "npc_sprite" and size != [1024, 1536]:
                self.error(where, "NPC plan size must be 1024x1536")
            elif rec.get("kind") == "creature_sprite" and size not in ([1024, 1536], [1536, 1536]):
                self.error(where, "creature size must be 1024x1536 or 1536x1536")
            attempts = self.sequence(rec.get("attempts"), where + ".attempts")
            if len(attempts) > 3:
                self.error(where, "attempt budget exceeded (initial + 2 corrections)")
            for attempt in attempts:
                a = self.mapping(attempt, where + ".attempts")
                if not a.get("tool") or a.get("outcome") not in {"review", "failed", "accepted"} or not isinstance(a.get("note"), str):
                    self.error(where, "attempt requires tool/outcome/note")
            reuse = rec.get("reuse_of")
            if reuse is not None:
                self.ref(reuse, self.items, where + ".reuse_of")
                seen = {aid}
                current = reuse
                while isinstance(current, str) and current in self.items:
                    if current in seen:
                        self.error(where, "reuse cycle")
                        break
                    seen.add(current)
                    other = self.items[current]
                    if not isinstance(other, dict):
                        break
                    if any(rec.get(k) != other.get(k) for k in ("kind", "size", "output")):
                        self.error(where, "reuse kind/size/output differs")
                        break
                    current = other.get("reuse_of")
                if attempts:
                    self.error(where, "reuse item must not spend generation attempts")
            fp = digest(canonical({"id": aid, "kind": rec.get("kind"), "output": output, "size": size, "relates_to": relates, "style_version": rec.get("style_version"), "prompt": rec.get("prompt"), "references": refs, "reuse_of": reuse, "content_fingerprint": self.fingerprint, "style_file_sha256": style_hash}))
            state = rec.get("status")
            reasons = []
            if rec.get("style_version") != style.get("version"):
                reasons.append("style version changed")
            if rec.get("input_fingerprint") != fp:
                reasons.append("input fingerprint changed or absent")
            if plan_doc.get("content_fingerprint") != self.fingerprint:
                reasons.append("content fingerprint changed or absent")
            asset = self.assets.get(aid)
            if state == "accepted":
                if not isinstance(asset, dict):
                    self.error(where, "accepted plan missing indexed asset")
                    reasons.append("missing indexed asset")
                else:
                    gen = self.mapping(asset.get("generation"), where + ".generation")
                    expected = {"plan_id": aid, "style_version": style.get("version"), "content_fingerprint": self.fingerprint, "input_fingerprint": fp}
                    for key, val in expected.items():
                        if gen.get(key) != val:
                            reasons.append(f"generation.{key} differs")
                    review = self.mapping(gen.get("review"), where + ".review")
                    if review.get("status") != "accepted" or not review.get("note"):
                        self.error(where, "indexed generation review is not accepted")
                    if not gen.get("tool") or not isinstance(gen.get("artistic_additions"), str):
                        self.error(where, "generation missing tool/artistic_additions")
                    if asset.get("file") != output:
                        self.error(where, "indexed file differs from plan output")
                    if not reuse and (not attempts or attempts[-1].get("outcome") != "accepted"):
                        self.error(where, "accepted item lacks successful attempt record")
                    path = self.path(asset.get("file"), where, self.root / "assets")
                    if not path or asset.get("sha256") != digest(path.read_bytes()):
                        reasons.append("accepted file missing or changed")
                action = "revise" if reasons else "skip"
            else:
                if asset is not None:
                    self.error(where, "unaccepted plan must not be indexed")
                if state == "review":
                    candidate = self.path(rec.get("candidate_file"), where + ".candidate_file", self.root / "assets")
                    if candidate and rec.get("sha256") != digest(candidate.read_bytes()):
                        self.error(where, "candidate hash mismatch")
                    action = "review" if not reasons else "revise"
                elif reuse:
                    action = "reuse"
                elif len(attempts) >= 3:
                    action = "blocked"
                    reasons.append("attempt budget exhausted")
                elif not available or state == "blocked_tool":
                    action = "blocked"
                    reasons.append("image tool unavailable; restore tool then mark planned")
                else:
                    action = "generate"
            if rec.get("batch") == "later" and style.get("status") != "approved" and action not in {"skip", "revise"}:
                action = "blocked"
                reasons.append("style not yet selected by user")
            if len(self.errors) > start_errors:
                action = "blocked"
                reasons.append("invalid item; fix errors before production")
            self.resume.append({"id": aid, "action": action, "reasons": reasons, "input_fingerprint": fp})
            if self.complete and action != "skip":
                self.error(where, f"incomplete: {action}")
        if any(x["action"] != "skip" for x in self.resume):
            self.warnings.append("Visual production incomplete; draft validation does not mean images delivered")
        outputs = {}
        for aid, rec in self.items.items():
            if not isinstance(rec, dict) or rec.get("reuse_of") is not None:
                continue
            output = rec.get("output")
            if isinstance(output, str) and output in outputs:
                self.error("asset_plan", f"duplicate output without reuse_of: {aid}, {outputs[output]}")
            if isinstance(output, str):
                outputs[output] = aid

    def run(self):
        try:
            self.prepare()
            if self.errors:
                return self.result()
            self.content()
            self.references()
            self.asset_files()
            self.production()
        except (ValueError, TypeError, KeyError, OSError, UnicodeError, RecursionError) as exc:
            self.error("module", f"malformed content: {exc}")
        return self.result()

    def result(self):
        return {"ok": not self.errors, "errors": self.errors, "warnings": self.warnings, "content_fingerprint": self.fingerprint, "resume": self.resume, "progress": {"planned": len(self.items), "indexed": len(self.assets), "reusable": sum(x["action"] == "skip" for x in self.resume)}}


def validate(root, complete=False):
    return Validator(Path(root), complete).run()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module", nargs="?", type=Path)
    parser.add_argument("--json", action="store_true", help="structured diagnostics and fingerprints")
    parser.add_argument("--complete", action="store_true", help="require all planned images accepted and current")
    parser.add_argument("--resume", action="store_true", help="include read-only per-item next actions")
    parser.add_argument("--self-test", action="store_true", help="run bundled offline tests")
    args = parser.parse_args()
    if args.self_test:
        tests = Path(__file__).resolve().parents[1] / "tests"
        suite = unittest.defaultTestLoader.discover(str(tests), pattern="test_*.py")
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    if not args.module:
        parser.error("MODULE_DIR required unless --self-test")
    result = validate(args.module, args.complete)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("PASS (authored draft only)" if result["ok"] else "FAIL")
        for level in ("errors", "warnings"):
            for message in result[level]:
                print(f"{level.upper()}: {message}")
        print(f"content_fingerprint: {result['content_fingerprint']}")
        print(f"progress: {result['progress']}")
        if args.resume:
            for item in result["resume"]:
                print(f"{item['id']}: {item['action']} {'; '.join(item['reasons'])}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
