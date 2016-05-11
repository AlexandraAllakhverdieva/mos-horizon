# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import contextlib
import logging
import os
from six import StringIO
import subprocess
from threading import Thread
from tempfile import mkdtemp
import time
import traceback
import uuid
from functools import wraps

from selenium.webdriver.common import action_chains
from selenium.webdriver.common import by
from selenium.webdriver.common import keys
from selenium.webdriver.remote.remote_connection import RemoteConnection
import testtools
import xvfbwrapper

from horizon.test import webdriver
from openstack_dashboard.test.integration_tests import config
from openstack_dashboard.test.integration_tests.pages import loginpage
from openstack_dashboard.test.integration_tests.regions import messages

ROOT_LOGGER = logging.getLogger()
ROOT_LOGGER.setLevel(logging.DEBUG)
LOGGER = logging.getLogger(__name__)
ROOT_PATH = os.path.dirname(os.path.abspath(config.__file__))
RemoteConnection.set_timeout(60)


def gen_random_resource_name(resource="", timestamp=True):
    """Generate random resource name using uuid and timestamp.

    Input fields are usually limited to 255 or 80 characters hence their
    provide enough space for quite long resource names, but it might be
    the case that maximum field length is quite restricted, it is then
    necessary to consider using shorter resource argument or avoid using
    timestamp by setting timestamp argument to False.
    """
    fields = ["horizon"]
    if resource:
        fields.append(resource)
    if timestamp:
        tstamp = time.strftime("%d-%m-%H-%M-%S")
        fields.append(tstamp)
    fields.append(str(uuid.uuid4()).replace("-", ""))
    return "_".join(fields)


def once_only(func):
    called_funcs = []

    @wraps(func)
    def wrapper(*args, **kwgs):
        if func.__name__ not in called_funcs:
            called_funcs.append(func.__name__)
            return func(*args, **kwgs)

    return wrapper


def ignore_skip(func):

    @wraps(func)
    def wrapper(self, exc_info):
        if exc_info[0].__name__ == 'SkipTest':
            return
        return func(self, exc_info)

    return wrapper


class VideoRecorder(object):

    def __init__(self, screencapture, polling_time=.2, frame_rate=2):
        self._screencapture = screencapture
        self._polling_time = polling_time
        self._frame_rate = frame_rate
        self._frame_path_tmpl = os.path.join(mkdtemp(), 'frame_%06d.png')

        self.is_launched = False

    def start(self):
        if self.is_launched:
            LOGGER.warn("video recording is already started")
            return

        def screencapture():
            i = 0
            while self.is_launched:
                i += 1
                try:
                    self._screencapture(self._frame_path_tmpl % i)

                except Exception as e:
                    LOGGER.warn("Detect exception during screencapture. Video "
                                "recording will be stopped. {}".format(e))
                    self.is_launched = False

                time.sleep(self._polling_time)

        self.is_launched = True
        self._t = Thread(target=screencapture)
        self._t.daemon = True
        self._t.start()

    def stop(self):
        if not self.is_launched:
            LOGGER.warn("video recording is already stopped")
            return

        self.is_launched = False

    def convert(self, dest_dir, file_name='movie'):
        if subprocess.call("which ffmpeg > /dev/null 2>&1", shell=True):
            LOGGER.warn("ffmpeg is not found, video converting is skipped")
            return

        dest_path = os.path.join(dest_dir, file_name)
        frames_dir = os.path.dirname(self._frame_path_tmpl)
        if not os.path.isdir(frames_dir):
            raise IOError(
                "Folder {!r} with frames is absent".format(frames_dir))

        subprocess.check_output(
            "ffmpeg -f image2 -r {} -i {} -vcodec mpeg4 -y {}.mp4 > /dev/null "
            "2>&1".format(self._frame_rate, self._frame_path_tmpl, dest_path),
            shell=True)


class BaseTestCase(testtools.TestCase):

    CONFIG = config.get_config()

    def setUp(self):
        self._configure_log()

        if not os.environ.get('INTEGRATION_TESTS', False):
            msg = "The INTEGRATION_TESTS env variable is not set."
            raise self.skipException(msg)

        # Start a virtual display server for running the tests headless.
        if os.environ.get('SELENIUM_HEADLESS', False):
            self.vdisplay = xvfbwrapper.Xvfb(width=1920, height=1080)
            args = []

            # workaround for memory leak in Xvfb taken from:
            # http://blog.jeffterrace.com/2012/07/xvfb-memory-leak-workaround.html
            args.append("-noreset")

            # disables X access control
            args.append("-ac")

            if hasattr(self.vdisplay, 'extra_xvfb_args'):
                # xvfbwrapper 0.2.8 or newer
                self.vdisplay.extra_xvfb_args.extend(args)
            else:
                self.vdisplay.xvfb_cmd.extend(args)
            self.vdisplay.start()

        # Start the Selenium webdriver and setup configuration.
        desired_capabilities = dict(webdriver.desired_capabilities)
        desired_capabilities['loggingPrefs'] = {'browser': 'ALL'}
        self.driver = webdriver.WebDriverWrapper(
            desired_capabilities=desired_capabilities
        )
        if self.CONFIG.selenium.maximize_browser:
            self.driver.maximize_window()
        self.driver.implicitly_wait(self.CONFIG.selenium.implicit_wait)
        self.driver.set_page_load_timeout(
            self.CONFIG.selenium.page_timeout)

        self.screencapture = VideoRecorder(self.driver.get_screenshot_as_file)
        self.screencapture.start()

        self.addOnException(self._attach_page_source)
        self.addOnException(self._attach_screenshot)
        self.addOnException(self._attach_video)
        self.addOnException(self._attach_browser_log)
        self.addOnException(self._attach_test_log)

        super(BaseTestCase, self).setUp()

    def _configure_log(self):
        """Configure log to capture test logs include selenium logs in order
        to attach them if test will be broken.
        """
        ROOT_LOGGER.handlers[:] = []  # clear other handlers to set target handler
        self._log_buffer = StringIO()
        stream_handler = logging.StreamHandler(stream=self._log_buffer)
        stream_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        stream_handler.setFormatter(formatter)
        ROOT_LOGGER.addHandler(stream_handler)

    @property
    def _test_report_dir(self):
        report_dir = os.path.join(ROOT_PATH, 'test_reports',
                                  '{}.{}'.format(self.__class__.__name__,
                                                 self._testMethodName))
        if not os.path.isdir(report_dir):
            os.makedirs(report_dir)
        return report_dir

    @ignore_skip
    def _attach_page_source(self, exc_info):
        source_path = os.path.join(self._test_report_dir, 'page.html')
        with self.log_exception("Attach page source"):
            with open(source_path, 'w') as f:
                f.write(self._get_page_html_source())

    @ignore_skip
    def _attach_screenshot(self, exc_info):
        screen_path = os.path.join(self._test_report_dir, 'screenshot.png')
        with self.log_exception("Attach screenshot"):
            self.driver.get_screenshot_as_file(screen_path)

    @ignore_skip
    def _attach_video(self, exc_info):
        with self.log_exception("Attach video"):
            self.screencapture.stop()
            self.screencapture.convert(self._test_report_dir)

    @ignore_skip
    def _attach_browser_log(self, exc_info):
        browser_log_path = os.path.join(self._test_report_dir, 'browser.log')
        with self.log_exception("Attach browser log"):
            with open(browser_log_path, 'w') as f:
                f.write(
                    self._unwrap_browser_log(self.driver.get_log('browser')))

    @ignore_skip
    def _attach_test_log(self, exc_info):
        test_log_path = os.path.join(self._test_report_dir, 'test.log')
        with self.log_exception("Attach test log"):
            with open(test_log_path, 'w') as f:
                f.write(self._log_buffer.getvalue().encode('utf-8'))

    @contextlib.contextmanager
    def log_exception(self, label):
        try:
            yield
        except Exception:
            self.addDetail(
                label, testtools.content.text_content(traceback.format_exc()))

    @staticmethod
    def _unwrap_browser_log(_log):
        def rec(log):
            if isinstance(log, dict):
                return log['message'].encode('utf-8')
            elif isinstance(log, list):
                return '\n'.join([rec(item) for item in log])
            else:
                return log.encode('utf-8')
        return rec(_log)

    def zoom_out(self, times=3):
        """Zooming out prevents different elements being driven out of xvfb
        viewport (which in Selenium>=2.50.1 prevents interaction with them.
        """
        html = self.driver.find_element(by.By.TAG_NAME, 'html')
        html.send_keys(keys.Keys.NULL)
        zoom_out_keys = (keys.Keys.SUBTRACT,) * times
        action_chains.ActionChains(self.driver).key_down(
            keys.Keys.CONTROL).send_keys(*zoom_out_keys).key_up(
            keys.Keys.CONTROL).perform()

    def _get_page_html_source(self):
        """Gets html page source.

        self.driver.page_source is not used on purpose because it does not
        display html code generated/changed by javascript.
        """
        html_elem = self.driver.find_element_by_tag_name("html")
        return html_elem.get_attribute("innerHTML").encode("utf-8")

    def tearDown(self):
        self.screencapture.stop()
        if os.environ.get('INTEGRATION_TESTS', False):
            self.driver.quit()
        if hasattr(self, 'vdisplay'):
            self.vdisplay.stop()
        super(BaseTestCase, self).tearDown()


class TestCase(BaseTestCase):

    ADMIN_NAME = BaseTestCase.CONFIG.identity.admin_username
    ADMIN_PASSWORD = BaseTestCase.CONFIG.identity.admin_password
    ADMIN_PROJECT = BaseTestCase.CONFIG.identity.admin_home_project

    DEMO_NAME = BaseTestCase.CONFIG.identity.username
    DEMO_PASSWORD = BaseTestCase.CONFIG.identity.password
    DEMO_PROJECT = BaseTestCase.CONFIG.identity.home_project

    TEST_USER_NAME = BaseTestCase.CONFIG.identity.username
    TEST_PASSWORD = BaseTestCase.CONFIG.identity.password
    HOME_PROJECT = BaseTestCase.CONFIG.identity.home_project

    def setUp(self):
        super(TestCase, self).setUp()
        self.login_pg = loginpage.LoginPage(self.driver, self.CONFIG)
        self.login_pg.go_to_login_page()
        self.zoom_out()

        self.create_demo_user()

        self.home_pg = self.login_pg.login(self.TEST_USER_NAME,
                                           self.TEST_PASSWORD)
        self.home_pg.change_project(self.HOME_PROJECT)
        self.assertTrue(
            self.home_pg.find_message_and_dismiss(messages.SUCCESS))
        self.assertFalse(
            self.home_pg.find_message_and_dismiss(messages.ERROR))

    @once_only
    def create_demo_user(self):
        self.home_pg = self.login_pg.login(self.ADMIN_NAME,
                                           self.ADMIN_PASSWORD)
        self.home_pg.change_project(self.ADMIN_PROJECT)

        projects_page = self.home_pg.go_to_identity_projectspage()
        if not projects_page.is_project_present(self.DEMO_PROJECT):
            projects_page.create_project(self.DEMO_PROJECT)

        users_page = self.home_pg.go_to_identity_userspage()
        if users_page.is_user_present(self.DEMO_NAME):
            users_page.delete_user(self.DEMO_NAME)
        users_page.create_user(self.DEMO_NAME, password=self.DEMO_PASSWORD,
                               project=self.DEMO_PROJECT, role='_member_')

        if self.home_pg.is_logged_in:
            self.home_pg.go_to_home_page()
            self.home_pg.log_out()

    def tearDown(self):
        try:
            if self.home_pg.is_logged_in:
                self.home_pg.go_to_home_page()
                self.home_pg.log_out()
        finally:
            super(TestCase, self).tearDown()


class AdminTestCase(TestCase):

    TEST_USER_NAME = TestCase.CONFIG.identity.admin_username
    TEST_PASSWORD = TestCase.CONFIG.identity.admin_password
    HOME_PROJECT = BaseTestCase.CONFIG.identity.admin_home_project
