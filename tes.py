import unittest
from fuzzywuzzy import fuzz
from collections import namedtuple

# Mocking a Role object as we don't have access to discord.Role in the test environment
Role = namedtuple('Role', ['name'])

class TestFuzzyMatching(unittest.TestCase):

    def test_fuzzy_matching(self):
        series_name = "All of My Female Apprentices Want to Kill Me"
        roles = [
            Role("Female"),
            Role("I Love the Demon Lord So Much That Even My Female Disciples Want to Kill Me"),
            Role("My Female Apprentices Want to Kill Me")
        ]

        best_match = None
        highest_score = 0

        for role in roles:
            # Skip roles with only one word
            if len(role.name.split()) == 1:
                continue

            score = fuzz.partial_ratio(series_name.lower(), role.name.lower())
            if score > highest_score:
                highest_score = score
                best_match = role

        # Verifying the best match and that it exceeds a threshold
        self.assertEqual(best_match.name, "")
        self.assertGreater(highest_score, 50)

if __name__ == '__main__':
    unittest.main()
