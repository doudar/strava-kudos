import contextlib
import io
import os
import unittest
from unittest.mock import Mock, patch

import give_kudos


class CredentialHandlingTests(unittest.TestCase):
    def test_driver_does_not_inherit_credentials_or_debug_settings(self):
        credentials = {
            'STRAVA_EMAIL': 'test@example.invalid',
            'STRAVA_PASSWORD': 'test-only-password',
            'DEBUG': 'pw:api',
            'PWDEBUG': '1',
        }
        driver = Mock()

        def start_driver():
            for key in credentials:
                self.assertNotIn(key, os.environ)
            return driver

        with patch.dict(os.environ, credentials, clear=True):
            with patch.object(give_kudos, 'sync_playwright') as factory:
                factory.return_value.start.side_effect = start_driver
                giver = give_kudos.KudosGiver()
                self.assertEqual(giver.EMAIL, credentials['STRAVA_EMAIL'])
                self.assertEqual(giver.PASSWORD, credentials['STRAVA_PASSWORD'])
                driver.firefox.launch.assert_called_once()

    def test_failure_output_omits_exception_values_and_tracebacks(self):
        for failure_phase in ('startup', 'login', 'kudos'):
            with self.subTest(phase=failure_phase):
                output = io.StringIO()
                secret_error = RuntimeError('fill("test-only-password") for test@example.invalid')
                with patch.object(give_kudos, 'KudosGiver') as factory:
                    if failure_phase == 'startup':
                        factory.side_effect = secret_error
                    elif failure_phase == 'login':
                        factory.return_value.email_login.side_effect = secret_error
                    else:
                        factory.return_value.give_kudos.side_effect = secret_error
                    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                        self.assertEqual(give_kudos.main(), 1)
                self.assertIn('Kudos run failed', output.getvalue())
                for sensitive_text in ('test-only-password', 'test@example.invalid', 'Traceback', 'fill('):
                    self.assertNotIn(sensitive_text, output.getvalue())

    def test_empty_credentials_fail_before_starting_playwright(self):
        with patch.dict(os.environ, {'STRAVA_EMAIL': '', 'STRAVA_PASSWORD': ''}, clear=True):
            with patch.object(give_kudos, 'sync_playwright') as factory:
                with self.assertRaises(Exception):
                    give_kudos.KudosGiver()
                factory.assert_not_called()

    def test_success_returns_zero(self):
        with patch.object(give_kudos, 'KudosGiver') as factory:
            self.assertEqual(give_kudos.main(), 0)
            factory.return_value.email_login.assert_called_once()
            factory.return_value.give_kudos.assert_called_once()


if __name__ == '__main__':
    unittest.main()
