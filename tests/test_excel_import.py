import glob
import os
import unittest

from trpg.excel_import import load_character_from_xlsx

_CHAR_DIR = os.path.join(os.path.dirname(__file__), "..", "characters")


def _first_xlsx():
    files = glob.glob(os.path.join(_CHAR_DIR, "*.xlsx"))
    return files[0] if files else None


@unittest.skipIf(_first_xlsx() is None, "characters 目录下无 xlsx 文件")
class TestExcelImport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.char = load_character_from_xlsx(_first_xlsx())

    def test_name_and_basic(self):
        self.assertIn("Richard", self.char.name)
        self.assertEqual(self.char.age, 39)
        self.assertEqual(self.char.occupation, "教授")

    def test_attributes(self):
        self.assertEqual(self.char.attributes["STR"], 65)
        self.assertEqual(self.char.attributes["CON"], 45)
        self.assertEqual(self.char.attributes["DEX"], 45)
        self.assertEqual(self.char.attributes["APP"], 65)
        self.assertEqual(self.char.attributes["POW"], 55)
        self.assertEqual(self.char.attributes["INT"], 75)
        self.assertEqual(self.char.attributes["SIZ"], 60)
        self.assertEqual(self.char.attributes["EDU"], 75)

    def test_derived(self):
        self.assertEqual(self.char.hp, 10)
        self.assertEqual(self.char.hp_max, 10)
        self.assertEqual(self.char.san, 55)
        self.assertEqual(self.char.san_max, 99)
        self.assertEqual(self.char.mp, 11)
        self.assertEqual(self.char.luck, 50)
        self.assertEqual(self.char.mov, 8)
        self.assertEqual(self.char.db, "+1D4")
        self.assertEqual(self.char.build, 1)

    def test_skills(self):
        self.assertEqual(self.char.skills["侦查"], 55)
        self.assertEqual(self.char.skills["聆听"], 60)
        self.assertEqual(self.char.skills["图书馆使用"], 55)
        self.assertEqual(self.char.skills["信用评级"], 40)
        self.assertEqual(self.char.skills["闪避"], 22)
        self.assertEqual(self.char.skills["斗殴"], 25)
        self.assertEqual(self.char.skills["手枪"], 20)
        self.assertEqual(self.char.skills["母语"], 75)
        self.assertEqual(self.char.skills["外语"], 50)
        self.assertEqual(self.char.skills["心理学"], 55)
        self.assertEqual(self.char.skills["克苏鲁神话"], 0)

    def test_resolve_aliases(self):
        self.assertEqual(self.char.resolve("图书馆"), 55)  # → 图书馆使用
        self.assertEqual(self.char.resolve("灵感"), 75)    # → 智力
        self.assertEqual(self.char.resolve("格斗"), 25)    # → 斗殴


if __name__ == "__main__":
    unittest.main()
