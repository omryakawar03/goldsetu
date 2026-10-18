import unittest

from app.security.credentials import hash_password, new_session_token, token_digest, verify_password
from app.security.permissions import Role, role_allows


class CredentialTests(unittest.TestCase):
    def test_password_hash_is_salted_and_verifies(self):
        first = hash_password("correct-horse-battery")
        second = hash_password("correct-horse-battery")
        self.assertNotEqual(first, second)
        self.assertTrue(verify_password("correct-horse-battery", first))
        self.assertFalse(verify_password("incorrect-password", first))

    def test_password_bounds_are_enforced(self):
        with self.assertRaises(ValueError):
            hash_password("short")

    def test_session_token_is_opaque_and_digest_is_deterministic(self):
        first = new_session_token()
        second = new_session_token()
        self.assertNotEqual(first, second)
        self.assertNotEqual(first, token_digest(first))
        self.assertEqual(token_digest(first), token_digest(first))


class PermissionTests(unittest.TestCase):
    def test_cashier_cannot_change_rates_refund_or_release_pledges(self):
        self.assertFalse(role_allows(Role.CASHIER, "rate:manage"))
        self.assertFalse(role_allows(Role.CASHIER, "payment:refund"))
        self.assertFalse(role_allows(Role.CASHIER, "pledge:release"))

    def test_owner_is_wildcard_and_unknown_role_is_denied(self):
        self.assertTrue(role_allows(Role.OWNER, "anything:new"))
        self.assertFalse(role_allows("unknown", "shop:read"))


if __name__ == "__main__":
    unittest.main()
