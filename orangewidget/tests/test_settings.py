import unittest

from orangewidget.settings import _cname, Setting


class SettingTest(unittest.TestCase):
    def test_nullable(self):
        self.assertTrue(Setting(None).nullable)
        self.assertFalse(Setting(42).nullable)

    def test_type(self):
        self.assertIsNone(Setting(None).type)
        self.assertIs(Setting({}).type, dict)

    def test_str(self):
        str(Setting(None))
        str(Setting(None, name="foo"))


class UtilsTest(unittest.TestCase):
    def test_cname(self):
        self.assertEqual(_cname(int), "int")
        self.assertEqual(_cname(dict), "dict")
        self.assertEqual(_cname(42), "int")
        self.assertEqual(_cname(42.0), "float")
        self.assertEqual(_cname({3: 4}), "dict")


if __name__ == "__main__":
    unittest.main()
