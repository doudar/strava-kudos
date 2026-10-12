import os
import sys
import time
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

BASE_URL = "https://www.strava.com/"


class LoginFailure(Exception):
    # Only these fixed messages may reach the log; never interpolate page data.
    STEPS = {
        'open': 'opening the login page',
        'email': 'filling the email field',
        'continue': 'submitting the email form',
        'password_option': 'waiting for a password option (Strava may require a code or verification)',
        'password': 'filling the password field',
        'submit': 'submitting the password form',
        'confirm': 'waiting for the dashboard (login was not confirmed)',
        'profile': 'loading the signed-in profile',
    }

    def __init__(self, step, timed_out=False):
        description = self.STEPS.get(step, 'an unknown login step')
        reason = 'Timed out' if timed_out else 'Failed'
        super().__init__(f'{reason} while {description}. No credential or page details logged.')

class KudosGiver:
    """
    Logins into Strava and gives kudos to all activities under
    Following.
    """
    def __init__(self, max_run_duration=540) -> None:
        # Keep credentials out of the environment inherited by the driver/browser.
        self.EMAIL = os.environ.pop('STRAVA_EMAIL', None)
        self.PASSWORD = os.environ.pop('STRAVA_PASSWORD', None)
        # Playwright debug output can include values passed to fill().
        os.environ.pop('DEBUG', None)
        os.environ.pop('PWDEBUG', None)
        if not self.EMAIL or not self.PASSWORD:
            raise Exception("Must set environ variables EMAIL AND PASSWORD. \
                e.g. run export STRAVA_EMAIL=YOUR_EMAIL")

        self.max_run_duration = max_run_duration
        self.start_time = time.time()
        self.num_entries = 100
        self.web_feed_entry_pattern = '[data-testid=web-feed-entry]'

        p = sync_playwright().start()
        self.browser = p.firefox.launch() # does not work in chrome
        self.page = self.browser.new_page()


    def email_login(self):
        """
        Login using email and password
        """
        step = 'open'
        try:
            self.page.goto(BASE_URL + 'login', wait_until='domcontentloaded')
            try:
                self.page.get_by_role("button", name="Reject", exact=True).click(timeout=5000)
            except PlaywrightTimeoutError:
                pass
            step = 'email'
            # Strava renders both mobile and desktop forms. Only use the visible one.
            email = self.page.locator('input[name="email"]:visible')
            password = self.page.locator('input[type="password"]:visible')
            email.fill(self.EMAIL)
            if not password.is_visible():
                step = 'continue'
                email.locator('xpath=ancestor::form[1]').locator('[type="submit"]').click()
                step = 'password_option'
                use_password = self.page.locator('[data-testid="use-password-cta"]:visible')
                password.or_(use_password).first.wait_for(state='visible')
                if use_password.is_visible():
                    use_password.click()
            step = 'password'
            password.fill(self.PASSWORD)
            step = 'submit'
            password.locator('xpath=ancestor::form[1]').locator('[type="submit"]').click()
            step = 'confirm'
            self.page.wait_for_url(
                lambda url: urlparse(url).hostname == 'www.strava.com'
                and urlparse(url).path.rstrip('/') == '/dashboard',
                wait_until='domcontentloaded',
            )
            step = 'profile'
            self._run_with_retries(func=self._get_page_and_own_profile)
        except Exception as error:
            raise LoginFailure(step, isinstance(error, PlaywrightTimeoutError)) from None
        print("---Logged in!!---")
        
    def _run_with_retries(self, func, retries=3):
        """
        Retry logic with sleep in between tries.
        """
        for i in range(retries):
            try:
                func()
                return
            except Exception:
                if i == retries - 1:
                    raise
                time.sleep(1)

    def _get_page_and_own_profile(self):
        """
        Limit activities count by GET parameter and get own profile ID.
        """
        self.page.goto(BASE_URL + f"dashboard?num_entries={self.num_entries}")

        ## Scrolling for lazy loading elements.
        for _ in range(5):
            self.page.keyboard.press('PageDown')
            time.sleep(0.5)
            self.page.keyboard.press('PageUp')

        self.own_profile_id = self.page.locator(".user-menu > a").get_attribute('href').split("/athletes/")[1]

    def locate_kudos_buttons_and_maybe_give_kudos(self, web_feed_entry_locator) -> int:
        """
        input: playwright.locator class
        Returns count of kudos given.
        """
        w_count = web_feed_entry_locator.count()
        given_count = 0
        print(f"web feeds found: {w_count}")
        for i in range(w_count):
            # run condition check
            curr_duration = time.time() - self.start_time
            if curr_duration > self.max_run_duration:
                print("Max run duration reached.")
                break

            web_feed = web_feed_entry_locator.nth(i)
            p_count = web_feed.get_by_test_id("entry-header").count()

            # check if feed item is a club post
            if self.is_club_post(web_feed):
                print('c', end='')
                continue

            # check if activity has multiple participants
            if p_count > 1:
                for j in range(p_count):
                    participant = web_feed.get_by_test_id("entry-header").nth(j)
                    # ignore own activities
                    if not self.is_participant_me(participant):
                        kudos_container = web_feed.get_by_test_id("kudos_comments_container").nth(j)
                        button = self.find_unfilled_kudos_button(kudos_container)
                        given_count += self.click_kudos_button(unfilled_kudos_container=button)
            else:
                # ignore own activities
                if not self.is_participant_me(web_feed):
                    button = self.find_unfilled_kudos_button(web_feed)
                    given_count += self.click_kudos_button(unfilled_kudos_container=button)
        print(f"\nKudos given: {given_count}")
        return given_count
    
    def is_club_post(self, container) -> bool:
        """
        Returns true if the container is a club post
        """
        if(container.get_by_test_id("group-header").count() > 0):
            return True
        
        if(container.locator(".clubMemberPostHeaderLinks").count() > 0):
            return True

        return False
    
    def is_participant_me(self, container) -> bool:
        """
        Returns true is the container's owner is logged-in user.
        """
        owner = self.own_profile_id
        try:
            h = container.get_by_test_id("owners-name").get_attribute('href')
            hl = h.split("/athletes/")
            owner = hl[1]
        except Exception as _:
            print("Some issue with getting owners-name container.")
        return owner == self.own_profile_id
    
    def find_unfilled_kudos_button(self, container):
        """
        Returns button as a playwright.locator class
        """
        button = None
        try:
            button = container.get_by_test_id("unfilled_kudos")
        except Exception as _:
            print("Some issue with finding the unfilled_kudos container.")
        return button

    def click_kudos_button(self, unfilled_kudos_container) -> int:
        """
        input: playwright.locator class
        Returns 1 if kudos button was clicked else 0
        """
        if unfilled_kudos_container.count() == 1:
            unfilled_kudos_container.click(timeout=0, no_wait_after=True)
            print('=', end='')
            time.sleep(1)
            return 1
        return 0

    def give_kudos(self):
        """
        Interate over web feed entries
        """
        ## Give Kudos on loaded page ##
        try:
            self.page.get_by_role("button", name="Accept").click(timeout=5000)
            print("Accepting updated terms.")
        except Exception as _:
            pass
        web_feed_entry_locator = self.page.locator(self.web_feed_entry_pattern)
        self.locate_kudos_buttons_and_maybe_give_kudos(web_feed_entry_locator=web_feed_entry_locator)
        self.browser.close()


def main():
    phase = "starting the browser (check credentials and container configuration)"
    try:
        kg = KudosGiver()
        phase = "signing into Strava"
        kg.email_login()
        phase = "giving kudos"
        kg.give_kudos()
    except LoginFailure as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        # Playwright exceptions can contain fill values and page data. Never print
        # the exception or traceback from a run that has access to credentials.
        print(f"Kudos run failed while {phase}. Error details suppressed to protect credentials.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
