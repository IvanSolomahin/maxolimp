import hashlib
import hmac
import json
import time
import unittest
from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from app.auth import hash_password, verify_init_data, verify_password
from app.routers.progress import period_bounds


class AuthProgressTests(unittest.TestCase):
    def test_password_hash_has_random_salt_and_verifies(self):
        first = hash_password('correct horse battery staple')
        second = hash_password('correct horse battery staple')
        self.assertNotEqual(first, second)
        self.assertTrue(verify_password('correct horse battery staple', first))
        self.assertFalse(verify_password('wrong password', first))

    def test_max_signature_and_expiry(self):
        token = 'test-bot-token'
        fields = {'auth_date': str(int(time.time())), 'user': json.dumps({'id': 123, 'first_name': 'Max'}, separators=(',', ':'))}
        check = '\n'.join(f'{key}={value}' for key, value in sorted(fields.items()))
        secret = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
        fields['hash'] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        self.assertEqual(verify_init_data(urlencode(fields), token)['id'], 123)
        self.assertIsNone(verify_init_data(urlencode(fields) + '&hash=duplicate', token))
        fields['auth_date'] = str(int(time.time()) - 3601)
        check = '\n'.join(f'{key}={value}' for key, value in sorted(fields.items()) if key != 'hash')
        fields['hash'] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        self.assertIsNone(verify_init_data(urlencode(fields), token))

    def test_period_boundaries_cross_year(self):
        now = datetime(2026, 1, 2, 0, 30, tzinfo=ZoneInfo('Europe/Moscow'))
        week_start, week_end, week = period_bounds('week', now)
        self.assertEqual(week_start.date().isoformat(), '2025-12-27')
        self.assertEqual(week_end.date().isoformat(), '2026-01-03')
        self.assertEqual(len(week), 7)
        month_start, month_end, days = period_bounds('month', now)
        self.assertEqual(month_start.date().isoformat(), '2025-12-04')
        self.assertEqual(month_end.date().isoformat(), '2026-01-03')
        self.assertEqual(len(days), 30)
        year_start, year_end, months = period_bounds('year', now)
        self.assertEqual(year_start.date().isoformat(), '2025-02-01')
        self.assertEqual(year_end.date().isoformat(), '2026-02-01')
        self.assertEqual(len(months), 12)


if __name__ == '__main__':
    unittest.main()
