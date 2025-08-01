# mypy: allow-untyped-defs

import base64
import json
import os
import subprocess
import tempfile
import threading
import traceback
import uuid

from mozprocess import ProcessHandler

from tools.serve.serve import make_hosts_file

from .base import (RefTestImplementation,
                   crashtest_result_converter,
                   testharness_result_converter,
                   reftest_result_converter,
                   TimedRunner)
from .process import ProcessTestExecutor
from .protocol import ConnectionlessProtocol
from ..browsers.base import browser_command


pytestrunner = None
webdriver = None


class ServoExecutor(ProcessTestExecutor):
    def __init__(self, logger, browser, server_config, timeout_multiplier, debug_info,
                 pause_after_test, reftest_screenshot="unexpected"):
        ProcessTestExecutor.__init__(self, logger, browser, server_config,
                                     timeout_multiplier=timeout_multiplier,
                                     debug_info=debug_info,
                                     reftest_screenshot=reftest_screenshot)
        self.pause_after_test = pause_after_test
        self.environment = {}
        self.protocol = ConnectionlessProtocol(self, browser)

        self.wpt_prefs_path = self.find_wpt_prefs()

        hosts_fd, self.hosts_path = tempfile.mkstemp()
        with os.fdopen(hosts_fd, "w") as f:
            f.write(make_hosts_file(server_config, "127.0.0.1"))

        self.env_for_tests = os.environ.copy()
        self.env_for_tests["HOST_FILE"] = self.hosts_path
        self.env_for_tests["RUST_BACKTRACE"] = "1"

    def teardown(self):
        try:
            os.unlink(self.hosts_path)
        except OSError:
            pass
        ProcessTestExecutor.teardown(self)

    def on_environment_change(self, new_environment):
        self.environment = new_environment
        return super().on_environment_change(new_environment)

    def on_output(self, line):
        line = line.decode("utf8", "replace")
        if self.interactive:
            print(line)
        else:
            self.logger.process_output(self.proc.pid, line, " ".join(self.command), self.test.url)

    def find_wpt_prefs(self):
        default_path = os.path.join("resources", "wpt-prefs.json")
        # The cwd is the servo repo for `./mach test-wpt`, but on WPT runners
        # it is the WPT repo. The nightly tar is extracted inside the python
        # virtual environment within the repo. This means that on WPT runners,
        # the cwd has the `_venv3/servo` directory inside which we find the
        # binary and the 'resources' directory.
        for dir in [".", "./_venv3/servo"]:
            candidate = os.path.abspath(os.path.join(dir, default_path))
            if os.path.isfile(candidate):
                return candidate
        self.logger.error("Unable to find wpt-prefs.json")
        return default_path

    def build_servo_command(self, test, extra_args=None):
        args = [
            "--hard-fail", "-u", "Servo/wptrunner",
            # See https://github.com/servo/servo/issues/30080.
            # For some reason rustls does not like the certificate generated by the WPT tooling.
            "--ignore-certificate-errors",
            "--enable-experimental-web-platform-features",
            "-z", self.test_url(test),
        ]
        for stylesheet in self.browser.user_stylesheets:
            args += ["--user-stylesheet", stylesheet]
        for pref, value in self.environment.get('prefs', {}).items():
            args += ["--pref", f"{pref}={value}"]
        args += ["--prefs-file", self.wpt_prefs_path]
        if self.browser.ca_certificate_path:
            args += ["--certificate-path", self.browser.ca_certificate_path]
        if extra_args:
            args += extra_args
        args += self.browser.binary_args
        debug_args, command = browser_command(self.binary, args, self.debug_info)
        if self.pause_after_test:
            command.remove("-z")
        return debug_args + command


class ServoTestharnessExecutor(ServoExecutor):
    convert_result = testharness_result_converter

    def __init__(self, logger, browser, server_config, timeout_multiplier=1, debug_info=None,
                 pause_after_test=False, **kwargs):
        ServoExecutor.__init__(self, logger, browser, server_config,
                               timeout_multiplier=timeout_multiplier,
                               debug_info=debug_info,
                               pause_after_test=pause_after_test)
        self.result_data = None
        self.result_flag = None

    def do_test(self, test):
        self.test = test
        self.result_data = None
        self.result_flag = threading.Event()

        self.command = self.build_servo_command(test)

        if not self.interactive:
            self.proc = ProcessHandler(self.command,
                                       processOutputLine=[self.on_output],
                                       onFinish=self.on_finish,
                                       env=self.env_for_tests,
                                       storeOutput=False)
            self.proc.run()
        else:
            self.proc = subprocess.Popen(self.command, env=self.env_for_tests)

        try:
            timeout = test.timeout * self.timeout_multiplier

            # Now wait to get the output we expect, or until we reach the timeout
            if not self.interactive and not self.pause_after_test:
                wait_timeout = timeout + 5
                self.result_flag.wait(wait_timeout)
            else:
                wait_timeout = None
                self.proc.wait()

            proc_is_running = True

            if self.result_flag.is_set():
                if self.result_data is not None:
                    result = self.convert_result(test, self.result_data)
                else:
                    self.proc.wait()
                    result = (test.make_result("CRASH", None), [])
                    proc_is_running = False
            else:
                result = (test.make_result("TIMEOUT", None), [])

            if proc_is_running:
                if self.pause_after_test:
                    self.logger.info("Pausing until the browser exits")
                    self.proc.wait()
                else:
                    self.proc.kill()
        except:  # noqa
            self.proc.kill()
            raise

        return result

    def on_output(self, line):
        prefix = "ALERT: RESULT: "
        decoded_line = line.decode("utf8", "replace")
        if decoded_line.startswith(prefix):
            try:
                self.result_data = json.loads(decoded_line[len(prefix):])
            except json.JSONDecodeError as error:
                self.logger.error(f"Could not process test output JSON: {error}")
            self.result_flag.set()
        else:
            ServoExecutor.on_output(self, line)

    def on_finish(self):
        self.result_flag.set()


class TempFilename:
    def __init__(self, directory):
        self.directory = directory
        self.path = None

    def __enter__(self):
        self.path = os.path.join(self.directory, str(uuid.uuid4()))
        return self.path

    def __exit__(self, *args, **kwargs):
        try:
            os.unlink(self.path)
        except OSError:
            pass


class ServoRefTestExecutor(ServoExecutor):
    convert_result = reftest_result_converter

    def __init__(self, logger, browser, server_config, binary=None, timeout_multiplier=1,
                 screenshot_cache=None, debug_info=None, pause_after_test=False,
                 reftest_screenshot="unexpected", **kwargs):
        ServoExecutor.__init__(self,
                               logger,
                               browser,
                               server_config,
                               timeout_multiplier=timeout_multiplier,
                               debug_info=debug_info,
                               reftest_screenshot=reftest_screenshot,
                               pause_after_test=pause_after_test)

        self.screenshot_cache = screenshot_cache
        self.reftest_screenshot = reftest_screenshot
        self.implementation = RefTestImplementation(self)
        self.tempdir = tempfile.mkdtemp()

    def reset(self):
        self.implementation.reset()

    def teardown(self):
        os.rmdir(self.tempdir)
        ServoExecutor.teardown(self)

    def screenshot(self, test, viewport_size, dpi, page_ranges):
        with TempFilename(self.tempdir) as output_path:
            extra_args = ["--exit",
                          "--output=%s" % output_path,
                          "--window-size", viewport_size or "800x600"]

            if dpi:
                extra_args += ["--device-pixel-ratio", dpi]

            self.command = self.build_servo_command(test, extra_args)

            if not self.interactive:
                self.proc = ProcessHandler(self.command,
                                           processOutputLine=[self.on_output],
                                           env=self.env_for_tests)

                try:
                    self.proc.run()
                    timeout = test.timeout * self.timeout_multiplier + 5
                    rv = self.proc.wait(timeout=timeout)
                except KeyboardInterrupt:
                    self.proc.kill()
                    raise
            else:
                self.proc = subprocess.Popen(self.command, env=self.env_for_tests)
                try:
                    rv = self.proc.wait()
                except KeyboardInterrupt:
                    self.proc.kill()
                    raise

            if rv is None:
                self.proc.kill()
                return False, ("EXTERNAL-TIMEOUT", None)

            if rv != 0 or not os.path.exists(output_path):
                return False, ("CRASH", None)

            with open(output_path, "rb") as f:
                # Might need to strip variable headers or something here
                data = f.read()
                # Returning the screenshot as a string could potentially be avoided,
                # see https://github.com/web-platform-tests/wpt/issues/28929.
                return True, [base64.b64encode(data).decode()]

    def do_test(self, test):
        self.test = test
        result = self.implementation.run_test(test)

        return self.convert_result(test, result)


class ServoTimedRunner(TimedRunner):
    def run_func(self):
        try:
            self.result = (True, self.func(self.protocol, self.url, self.timeout))
        except Exception as e:
            message = getattr(e, "message", "")
            if message:
                message += "\n"
            message += traceback.format_exc(e)
            self.result = False, ("INTERNAL-ERROR", message)
        finally:
            self.result_flag.set()

    def set_timeout(self):
        pass


class ServoCrashtestExecutor(ServoExecutor):
    convert_result = crashtest_result_converter

    def __init__(self, logger, browser, server_config, binary=None, timeout_multiplier=1,
                 screenshot_cache=None, debug_info=None, pause_after_test=False,
                 **kwargs):
        ServoExecutor.__init__(self,
                               logger,
                               browser,
                               server_config,
                               timeout_multiplier=timeout_multiplier,
                               debug_info=debug_info,
                               pause_after_test=pause_after_test)

        self.pause_after_test = pause_after_test
        self.protocol = ConnectionlessProtocol(self, browser)

    def do_test(self, test):
        timeout = (test.timeout * self.timeout_multiplier if self.debug_info is None
                   else None)

        test_url = self.test_url(test)
        # We want to pass the full test object into build_servo_command,
        # so stash it in the class
        self.test = test
        success, data = ServoTimedRunner(self.logger, self.do_crashtest, self.protocol,
                                         test_url, timeout, self.extra_timeout).run()
        # Ensure that no processes hang around if they timeout.
        self.proc.kill()

        if success:
            return self.convert_result(test, data)

        return (test.make_result(*data), [])

    def do_crashtest(self, protocol, url, timeout):
        self.command = self.build_servo_command(self.test, extra_args=["-x"])

        if not self.interactive:
            self.proc = ProcessHandler(self.command,
                                       env=self.env_for_tests,
                                       processOutputLine=[self.on_output],
                                       storeOutput=False)
            self.proc.run()
        else:
            self.proc = subprocess.Popen(self.command, env=self.env_for_tests)

        self.proc.wait()

        if self.proc.poll() >= 0:
            return {"status": "PASS", "message": None}
        return {"status": "CRASH", "message": None}
