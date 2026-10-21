import glob
import os
import tempfile
import unittest

from trpg.character import Character
from trpg.roster import Roster, _slug

_CHAR_DIR = os.path.join(os.path.dirname(__file__), "..", "characters")
_HAS_XLSX = bool(glob.glob(os.path.join(_CHAR_DIR, "*.xlsx")))


def make_char(name: str) -> Character:
    return Character(
        name=name, age=30, occupation="",
        attributes={"STR": 50, "CON": 50, "DEX": 50, "APP": 50, "POW": 50, "INT": 50, "SIZ": 50, "EDU": 50},
        skills={"侦查": 50}, hp=10, hp_max=10, san=50, san_max=99, mp=10, mp_max=10, luck=50,
    )


class TestSlug(unittest.TestCase):
    def test_slug_ascii(self):
        self.assertEqual(_slug("Alice"), "alice")
        self.assertEqual(_slug("Richard James Henderson"), "richard-james-henderson")

    def test_slug_pure_cjk_falls_back(self):
        self.assertEqual(_slug("张三"), "char")


class TestRosterAdd(unittest.TestCase):
    def test_add_auto_slug(self):
        r = Roster()
        cid = r.add(make_char("Alice"))
        self.assertEqual(cid, "alice")
        self.assertEqual(r.active.name, "Alice")

    def test_first_auto_activates(self):
        r = Roster()
        r.add(make_char("Alice"))
        r.add(make_char("Bob"), activate=False)
        self.assertEqual(r.active.name, "Alice")

    def test_add_activates_by_default(self):
        r = Roster()
        r.add(make_char("Alice"))
        r.add(make_char("Bob"))
        self.assertEqual(r.active.name, "Bob")

    def test_duplicate_name_dedup(self):
        r = Roster()
        a = r.add(make_char("Alice"))
        b = r.add(make_char("Alice"))
        self.assertEqual(a, "alice")
        self.assertEqual(b, "alice-2")

    def test_explicit_cid_overwrites(self):
        r = Roster()
        r.add(make_char("Alice"), cid="hero")
        self.assertEqual(len(r), 1)
        r.add(make_char("Bob"), cid="hero")
        self.assertEqual(len(r), 1)  # 覆盖，不新增
        self.assertEqual(r.characters["hero"].name, "Bob")


class TestRosterSwitch(unittest.TestCase):
    def test_switch(self):
        r = Roster()
        a = r.add(make_char("Alice"))
        b = r.add(make_char("Bob"))
        self.assertEqual(r.active_id, b)
        r.switch(a)
        self.assertEqual(r.active.name, "Alice")
        r.switch(b)
        self.assertEqual(r.active.name, "Bob")

    def test_switch_unknown_raises(self):
        with self.assertRaises(KeyError):
            Roster().switch("nobody")


class TestRosterRemove(unittest.TestCase):
    def test_remove_active_falls_back(self):
        r = Roster()
        a = r.add(make_char("Alice"))
        b = r.add(make_char("Bob"))
        r.remove(b)  # b 是当前激活
        self.assertNotIn(b, r.characters)
        self.assertEqual(r.active_id, a)


class TestRosterPersist(unittest.TestCase):
    def test_save_load_roundtrip(self):
        r = Roster()
        a = r.add(make_char("Alice"))
        b = r.add(make_char("Bob"))
        r.characters[a].apply_damage(3)
        with tempfile.TemporaryDirectory() as d:
            r.save(d)
            r2 = Roster.load(d)
        self.assertEqual(set(r2.characters), {a, b})
        self.assertEqual(r2.characters[a].hp, 7)
        self.assertEqual(r2.active_id, b)


@unittest.skipIf(not _HAS_XLSX, "characters 目录下无 xlsx")
class TestRosterImportDir(unittest.TestCase):
    def test_import_dir(self):
        r = Roster.import_dir(_CHAR_DIR)
        self.assertGreaterEqual(len(r), 1)
        self.assertIsNotNone(r.active)
        self.assertTrue(any("Richard" in cid for cid, _ in r.list()))

    def test_import_xlsx_id_is_stem(self):
        p = glob.glob(os.path.join(_CHAR_DIR, "*.xlsx"))[0]
        r = Roster()
        cid = r.import_xlsx(p)
        self.assertIn("Richard", cid)


if __name__ == "__main__":
    unittest.main()
