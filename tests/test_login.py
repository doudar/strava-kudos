import contextlib
import io
import unittest
from unittest.mock import Mock, patch

from playwright.sync_api import sync_playwright

from give_kudos import KudosGiver, LoginFailure


class LoginFlowTests(unittest.TestCase):
    """Exercise real Firefox selectors against fixtures; all requests are intercepted."""

    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.firefox.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.set_default_timeout(1500)
        self.page.set_default_navigation_timeout(1500)
        self.giver = KudosGiver.__new__(KudosGiver)
        self.giver.page = self.page
        self.giver.EMAIL = 'test@example.invalid'
        self.giver.PASSWORD = 'test-only-password'
        self.giver._get_page_and_own_profile = Mock()

    def tearDown(self):
        self.context.close()

    def serve_login(self, combined=False, password_option=False, rejected=False, code_only=False):
        # Hidden mobile controls and unrelated login buttons must not be selected.
        password_form = '<form onsubmit="finish(event)"><input type="password" name="password"><button type="submit">Log In</button></form>'
        option = '<button data-testid="use-password-cta" onclick="showPassword()">Use password</button>'
        html = '''<!doctype html><html><body>
          <button>Log In</button><button>Reject</button>
          <form style="display:none"><input name="email"><input type="password"><button type="submit">Log In</button></form>
          <div id="active"><form onsubmit="continueLogin(event)">
            <label>Email<input name="email" type="email"></label>
            COMBINED_PASSWORD
            <button type="submit">Log In</button>
          </form></div>
          <script>
            function finish(event) {
              event.preventDefault();
              if (!REJECTED) location.href = '/dashboard';
            }
            function showPassword() { document.querySelector('#active').innerHTML = PASSWORD_FORM; }
            function continueLogin(event) {
              event.preventDefault();
              if (COMBINED) { finish(event); return; }
              setTimeout(() => {
                if (CODE_ONLY) document.querySelector('#active').innerHTML = '<input autocomplete="one-time-code">';
                else if (PASSWORD_OPTION) document.querySelector('#active').innerHTML = OPTION;
                else showPassword();
              }, 50);
            }
          </script></body></html>'''
        import json
        for name, value in {
            'COMBINED_PASSWORD': '<input type="password" name="password">' if combined else '',
            'PASSWORD_FORM': json.dumps(password_form),
            'PASSWORD_OPTION': json.dumps(password_option),
            'CODE_ONLY': json.dumps(code_only),
            'COMBINED': json.dumps(combined),
            'REJECTED': json.dumps(rejected),
            'OPTION': json.dumps(option),
        }.items():
            html = html.replace(name, value)

        def route_request(route):
            if route.request.url == 'https://www.strava.com/login':
                route.fulfill(body=html, content_type='text/html')
            elif route.request.url == 'https://www.strava.com/dashboard':
                route.fulfill(body='<h1>Dashboard</h1>', content_type='text/html')
            else:
                route.abort()

        self.context.route('**/*', route_request)

    def test_email_first_form(self):
        self.serve_login()
        self.giver.email_login()
        self.giver._get_page_and_own_profile.assert_called_once()

    def test_combined_form_with_password_without_textbox_role(self):
        self.serve_login(combined=True)
        self.giver.email_login()
        self.giver._get_page_and_own_profile.assert_called_once()

    def test_optional_password_choice(self):
        self.serve_login(password_option=True)
        self.giver.email_login()
        self.giver._get_page_and_own_profile.assert_called_once()

    def test_rejected_login_does_not_report_success_or_load_profile(self):
        self.serve_login(rejected=True)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaisesRegex(LoginFailure, 'dashboard') as error:
                self.giver.email_login()
        self.assertNotIn('Logged in', output.getvalue())
        self.assertNotIn(self.giver.EMAIL, str(error.exception))
        self.assertNotIn(self.giver.PASSWORD, str(error.exception))
        self.giver._get_page_and_own_profile.assert_not_called()

    def test_code_only_flow_stops_without_bypassing_verification(self):
        self.serve_login(code_only=True)
        with self.assertRaisesRegex(LoginFailure, 'may require a code or verification'):
            self.giver.email_login()
        self.giver._get_page_and_own_profile.assert_not_called()


class LoginErrorTests(unittest.TestCase):
    def test_unknown_diagnostic_cannot_echo_sensitive_values(self):
        message = str(LoginFailure('test-only-password test@example.invalid', timed_out=True))
        self.assertEqual(message, 'Timed out while an unknown login step. No credential or page details logged.')

    def test_retry_uses_last_attempt(self):
        giver = KudosGiver.__new__(KudosGiver)
        operation = Mock(side_effect=[RuntimeError(), RuntimeError(), None])
        with patch('give_kudos.time.sleep'):
            giver._run_with_retries(operation, retries=3)
        self.assertEqual(operation.call_count, 3)


if __name__ == '__main__':
    unittest.main()
