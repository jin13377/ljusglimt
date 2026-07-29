import copy
import unittest

from scripts.assign_user_images_offline import assign


class OfflineUserImageTests(unittest.TestCase):
    def manifest(self):
        return {
            "images": [
                {"id": "animal-collage", "category_scores": {"Djur": 0.8, "Hälsa": 0.1, "Framsteg": 0.2}},
                {"id": "health-collage", "category_scores": {"Djur": 0.1, "Hälsa": 0.9, "Framsteg": 0.3}},
            ]
        }

    def article(self, article_id, category):
        return {
            "id": article_id,
            "title": article_id,
            "category": category,
            "source_fingerprint": "a" * 20,
        }

    def test_assigns_best_unused_collage_by_category(self):
        data = {"items": [self.article("dog", "Djur"), self.article("care", "Hälsa")]}
        preserved, assigned = assign(data, self.manifest())
        self.assertEqual((preserved, assigned), (0, 2))
        self.assertEqual(data["items"][0]["user_image"]["user_image_id"], "animal-collage")
        self.assertEqual(data["items"][1]["user_image"]["user_image_id"], "health-collage")
        self.assertEqual(len({item["user_image"]["user_image_id"] for item in data["items"]}), 2)

    def test_preserves_valid_assignment_and_uses_remaining_image(self):
        first = self.article("dog", "Djur")
        first["user_image"] = {
            "url": "/news-images/user/health-collage.webp",
            "alt": "Existing",
            "user_image_id": "health-collage",
            "width": 1280,
            "height": 848,
        }
        data = {"items": [first, self.article("care", "Hälsa")]}
        preserved, assigned = assign(data, self.manifest())
        self.assertEqual((preserved, assigned), (1, 1))
        self.assertEqual(data["items"][1]["user_image"]["user_image_id"], "animal-collage")

    def test_primary_image_removes_stale_user_assignment(self):
        item = self.article("source", "Djur")
        item["source_image_verified"] = True
        item["source_image_url"] = "https://example.com/photo.jpg"
        item["user_image"] = {
            "url": "/news-images/user/animal-collage.webp",
            "alt": "Old",
            "user_image_id": "animal-collage",
            "width": 1280,
            "height": 848,
        }
        data = {"items": [copy.deepcopy(item)]}
        self.assertEqual(assign(data, self.manifest()), (0, 0))
        self.assertNotIn("user_image", data["items"][0])


if __name__ == "__main__":
    unittest.main()
