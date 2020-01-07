import unittest

from orangewidget.settings import is_setting_type_supported


class TestSupportedSettingTypes(unittest.TestCase):
    def test_primitive_types(self):
        self.assertTrue(is_setting_type_supported(None))
        self.assertTrue(is_setting_type_supported(0))
        self.assertTrue(is_setting_type_supported(0.1))
        self.assertTrue(is_setting_type_supported("foo"))
        self.assertTrue(is_setting_type_supported(bytes(1)))

    def test_composite_types(self):
        self.assertTrue(is_setting_type_supported(["foo", "bar"]))
        self.assertTrue(is_setting_type_supported(("foo", "bar")))
        self.assertTrue(is_setting_type_supported({"foo": 1, "bar": 2}))
        self.assertTrue(is_setting_type_supported(set(("foo", "bar"))))
        self.assertTrue(is_setting_type_supported(frozenset(("foo", "bar"))))
        self.assertFalse(is_setting_type_supported(range(2)))

    def test_nested_types(self):
        values = [[1, 2], (2, (3, 4, ["Foo", set(("foo", "bar"))]))]
        self.assertTrue(is_setting_type_supported(values))
        values = [[1, 2], (2, (3, 4, ["Foo", range(3)]))]
        self.assertFalse(is_setting_type_supported(values))


if __name__ == "__main__":
    unittest.main()
