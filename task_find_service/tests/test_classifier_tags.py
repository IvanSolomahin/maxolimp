import unittest

from app.services.classifier_tags import normalize_tags, split_source_classifier


class ClassifierTagsTests(unittest.TestCase):
    def test_split_trim_and_deduplicate_combined_classifier(self):
        self.assertEqual(
            split_source_classifier("Алгебра. Действия с корнями , Алгебра. Действия с числами , Алгебра. Действия с корнями , Геометрия"),
            ["Алгебра. Действия с корнями", "Алгебра. Действия с числами", "Геометрия"],
        )

    def test_keep_commas_inside_tag_names(self):
        name = "Алгебра. Многочлены (делимость, Безу, Виет, бином...)"
        self.assertEqual(split_source_classifier(f"{name} , Геометрия"), [name, "Геометрия"])
        self.assertEqual(normalize_tags([name, f" {name} "]), [name])


if __name__ == "__main__":
    unittest.main()
