from __future__ import print_function

import os
import sys
import re
import atexit
from signal import signal, SIGABRT, SIGINT, SIGTERM
import logging
import webbrowser
try:
    from shlex import quote
except ImportError:
    from pipes import quote

from pexpect import pxssh

from .version import __version__
from .utils import (join_cmd, check_dns, try_quit_xquartz, check_port_occupied)
from .pysectools import (zero, Pinentry, PINENTRY_PATH)
from .config_manager import (JRMT_DEFAULTS, CFG_SEARCH_LOCATIONS,
                             generate_config_file, get_base_arg_parser, ConfigManager)

JP_SITE_PATTERN_FORMAT = "\s(https?://((localhost)|(127\.0\.0\.1)):{port}[\w\-./%?=]+)\s"

if hasattr(sys.stdout, 'buffer'):
    STDOUT_BUFFER = sys.stdout.buffer
else:
    STDOUT_BUFFER = sys.stdout


class CustomSSH(pxssh.pxssh):
    def login(self, server, username, password='', *args, **kwargs):
        """Login to an SSH server while checking the DNS, silencing logs,
        and suppressing the traceback for pxssh exceptions (such as incorrect password errors).
        :return: True if login is successful
        """
        logger = logging.getLogger(__name__)
        try:
            logger.debug("RUN: ssh {}@{}".format(username, server))
            dns_err, host = check_dns(server)
            if dns_err == 1:
                logger.debug("RUN: ssh {}@{}".format(username, host))
            elif dns_err == 2:
                logger.error("Unable to resolve server.")
                return False
            self.force_password = True
            self.silence_logs()
            return super(CustomSSH, self).login(host, username, password, *args, **kwargs)
        except pxssh.ExceptionPxssh as err:
            logger.error("pxssh error: {}".format(err))
            return False

    def silence_logs(self):
        """Prevent printing into any logfile.
        :return: previous logfile, logfile_read, logfile_send"""
        logfile, logfile_read, logfile_send = self.logfile, self.logfile_read, self.logfile_send
        self.logfile, self.logfile_read, self.logfile_send = None, None, None
        return logfile, logfile_read, logfile_send

    def sendline(self, s='', silence=True):
        """Send s, and log s to logger.debug() if silence == False"""
        if not silence:
            logger = logging.getLogger(__name__)
            logger.debug("SEND: {}".format(s))
        return super(CustomSSH, self).sendline(s)

    def sendlineprompt(self, s='', timeout=-1, silence=True, check_exit_status=False):
        """Send s with sendline() and then prompt() once.
        :param s: the string to send
        :param timeout: number of seconds to wait for prompt; use default if -1; no timeout if None
        :param silence: silence printing of s to debug log
        :param check_exit_status: check the exit status and print a warning if the command exited with an error
        :return: output of sendline(), output of prompt()
        """
        value = self.sendline(s, silence)
        prompt = self.prompt(timeout)
        if check_exit_status and not silence:
            exit_code = self.get_exit_code()
            exit_message = self.before.split(b'\n')[-2].strip().decode()
            if not exit_message:
                exit_message = "<no message>"
            if exit_code > 0:
                logger = logging.getLogger(__name__)
                logger.warning("ERROR: in: {0}\n    code {1}: {2}".format(s, exit_code, exit_message))
        return value, prompt

    def sendpass(self, password, restore_logs=False):
        """Silence all logfiles and send password as a line.
        :param password: The password
        :param restore_logs: Restore the previous logfiles after sending the password
        """
        logfile, logfile_read, logfile_send = self.silence_logs()
        return_val = self.sendline(password, silence=True)
        if restore_logs:
            self.logfile, self.logfile_read, self.logfile_send = logfile, logfile_read, logfile_send
        return return_val

    def get_exit_code(self):
        """Get the exit code of the previous command.
        Maintains the `self.before`, `self.match`, and `self.after` variables.
        :return: The exit code as an int
        """
        before, match, after = self.before, self.match, self.after
        self.sendlineprompt("echo $?", silence=True)
        # TODO: use regex to find the exit code instead of splitting
        exit_code = int(self.before.split(b'\n')[1].strip())
        self.before, self.match, self.after = before, match, after
        return exit_code

    def get_hostname(self):
        """Get the server's hostname
        Maintains the `self.before`, `self.match`, and `self.after` variables.
        :return: the hostname
        """
        before, match, after = self.before, self.match, self.after
        self.sendlineprompt("hostname", silence=True)
        hostname = self.before.decode('utf-8').strip().split('\n')[1]
        self.before, self.match, self.after = before, match, after
        return hostname

    def digest_all_prompts(self, timeout=0.5):
        """Digest all prompts until there is a delay of <timeout>."""
        if timeout == -1:
            timeout = self.timeout
        while self.prompt(timeout):
            pass


class FilteredOut(object):
    def __init__(self, txtctrl, by, reactions=None):
        self.txtctrl = txtctrl
        self.by = by
        self.reactions = reactions

    def write(self, bytestr):
        # TODO: split bytestr by lines first, and only print lines starting with self.by
        # to prevent inadvertent printing of password prompts or other unwanted lines
        # (the password itself shouldn't go through this function anyway so it is mostly a cosmetic issue)
        try:
            if isinstance(self.by, list) and any(by in bytestr for by in self.by):
                self.txtctrl.write(bytestr)
            elif bytestr[:len(self.by)] == self.by:
                self.txtctrl.write(bytestr)
            if self.reactions is not None:
                for key in self.reactions.keys():
                    if key in bytestr:
                        self.reactions[key]()
        except IndexError:
            pass

    def flush(self):
        self.txtctrl.flush()

    def exit_on_find(self, bytestr):
        if self.by in bytestr:
            sys.exit(0)
        return bytestr


class JupyterRemoteException(Exception):
    pass


class JupyterRemoteError(JupyterRemoteException):
    pass


class JupyterRemote(object):
    def __init__(
            self,
            config=None,
            user=JRMT_DEFAULTS.get("DEFAULT_USER"),
            host=JRMT_DEFAULTS.get("DEFAULT_HOST"),
            subcommand=JRMT_DEFAULTS.get("DEFAULT_JP_SUBCOMMAND"),
            jp_port=JRMT_DEFAULTS.get("DEFAULT_JP_PORT"),
            port_retries=JRMT_DEFAULTS.get("PORT_RETRIES"),
            jp_time=JRMT_DEFAULTS.get("DEFAULT_JP_TIME"),
            jp_mem=JRMT_DEFAULTS.get("DEFAULT_JP_MEM"),
            jp_cores=JRMT_DEFAULTS.get("DEFAULT_JP_CORES"),
            keepalive=False,
            keepxquartz=False,
            forcegetpass=JRMT_DEFAULTS.get("FORCE_GETPASS"),
            no_browser=False,
            forwardx11=True,
            forwardx11trusted=False,
    ):
        self.logger = logging.getLogger(__name__)

        self.user = user
        self.host = host
        self.subcommand = subcommand
        self.keep_alive = keepalive
        self.keep_xquartz = keepxquartz
        self.no_browser = no_browser

        if config is None:
            config = ConfigManager().config

        module_load_call = config.get('Settings', 'MODULE_LOAD_CALL')
        source_jupyter_call = config.get('Settings', 'SOURCE_JUPYTER_CALL')
        init_jupyter_commands = config.get('Settings', 'INIT_JUPYTER_COMMANDS')
        jp_call_format = config.get('Settings', 'RUN_JUPYTER_CALL_FORMAT')

        self.run_internal_session = config.getboolean('Remote Environment Settings', 'USE_INTERNAL_INTERACTIVE_SESSION')
        srun_call_format = config.get('Remote Environment Settings', 'INTERACTIVE_CALL_FORMAT')
        self.srun_timeout = config.get('Remote Environment Settings', 'START_INTERACTIVE_SESSION_TIMEOUT')
        self.srun_usepass = config.getboolean('Remote Environment Settings', 'INTERACTIVE_REQUIRES_PASSWORD')
        self.internal_ssh_usepass = config.getboolean('Remote Environment Settings', 'INTERNAL_SSH_REQUIRES_PASSWORD')
        password_request_pattern = config.get('Remote Environment Settings', 'PASSWORD_REQUEST_PATTERN')
        self.password_request_pattern = re.compile(password_request_pattern.encode('utf-8'))

        # find an open port starting with the supplied port
        success = False
        for port in range(jp_port, jp_port + port_retries + 1):
            port_occupied = check_port_occupied(port)
            if port_occupied:
                self.logger.debug("Port {0} is not available, error {1}: {2}".format(
                    port, port_occupied.errno, port_occupied.strerror))
            else:
                self.logger.debug("Port {} is available, using for Jupyter-Remote.".format(port))
                self.jp_port = port
                success = True
                break
        if not success:
            self.logger.error("Port {0} and the next {1} ports are already occupied.".format(jp_port, port_retries))
            raise JupyterRemoteError("Could not find an available port.")
        self.logger.debug("")

        self.srun_call = srun_call_format.format(
            time=quote(jp_time),
            mem=quote(jp_mem),
            cores=jp_cores
        )
        try:
            self.srun_timeout = int(self.srun_timeout)
        except (ValueError, TypeError):
            if self.srun_timeout in ["None", "inf"]:
                self.srun_timeout = None
            else:
                self.srun_timeout = -1
        if self.run_internal_session:
            self.logger.debug("Will start internal interactive session with command:\n    {}".format(self.srun_call))
            self.logger.debug(
                "Will {} password when starting interactive session\n"
                "Will {} password with ssh-ing into interactive session\n".format(
                    "send" if self.srun_usepass else "not send",
                    "send" if self.internal_ssh_usepass else "not send"
                ))

        self.init_jupyter_commands = []
        if module_load_call:
            module_load_call = module_load_call.strip("module load ")
            self.init_jupyter_commands.append(join_cmd("module load", module_load_call))
        if source_jupyter_call:
            source_jupyter_call = source_jupyter_call.strip("source ")
            self.init_jupyter_commands.append(join_cmd("source", source_jupyter_call))
        if init_jupyter_commands:
            self.init_jupyter_commands.extend(init_jupyter_commands.strip().split('\n'))
        self.logger.debug("\n    ".join(["Will initialize Jupyter with commands:"] + self.init_jupyter_commands))

        self.jp_call = jp_call_format.format(
            subcommand=quote(subcommand),
            port=self.jp_port
        )
        self.logger.debug("Will run Jupyter with command:\n    {}\n".format(self.jp_call))

        self.__pass = ""
        self._pinentry = Pinentry(pinentry_path=PINENTRY_PATH, fallback_to_getpass=True, force_getpass=forcegetpass)

        login_ssh_options = {
            "LocalForward": "{} 127.0.0.1:{}".format(jp_port, jp_port),
            "PubkeyAuthentication": "no"
        }
        if forwardx11:
            login_ssh_options["ForwardX11"] = "yes"
        if forwardx11trusted:
            login_ssh_options["ForwardX11Trusted"] = "yes"

        self._login_ssh = CustomSSH(timeout=60, ignore_sighup=False, options=login_ssh_options)

        self._second_ssh = CustomSSH(timeout=10, ignore_sighup=False, options={"PubkeyAuthentication": "no"})

        # perform close() on exit or term() on interrupt
        atexit.register(self.close)
        self.flag_exit = False
        for sig in (SIGABRT, SIGINT, SIGTERM):
            signal(sig, self.term)

    def run(self):
        """Run the standard JupyterRemote sequence"""
        self.ask_for_pin()
        if self.connect() or self.keep_alive:
            self.logger.debug("Starting pexpect interactive mode.")
            self.interact()

    def ask_for_pin(self):
        """Prompt for a password"""
        self.__pass = self._pinentry.ask(
            prompt="Enter your passphrase: ",
            description="Connect to remote server for jupyter {}".format(self.subcommand),
            error="No password entered",
            validator=lambda x: x is not None and len(x) > 0
        )
        self._pinentry.close()

    def connect(self):
        """Connect to Jupyter

        First SSH into an interactive node and run jupyter.
        Then SSH into that node to set up forwarding.
        Finally, open the jupyter notebook page in the browser.

        :return: True if connection is successful
        """
        # start login ssh
        self.logger.info("Connecting to {}@{}".format(self.user, self.host))
        if not self._login_ssh.login(self.host, self.user, self.__pass):
            return False
        self.logger.debug("Connected.")

        # get the login hostname
        jp_login_host = self._login_ssh.get_hostname()
        self.logger.info("Hostname: {}\n".format(jp_login_host))

        if self.run_internal_session:
            # start an interactive session and get the name of the interactive node
            jp_interactive_host = self.start_interactive_session(self._login_ssh)
            if jp_interactive_host is False:
                return False
        else:
            jp_interactive_host = None

        # start jupyter and get the URL
        jp_site = self.start_jupyter(self._login_ssh)
        
        if self.run_internal_session:
            # log in to the second ssh
            self.logger.info("\nStarting a second connection to the login node.")
            if not self._second_ssh.login(jp_login_host, self.user, self.__pass):
                return False
            self.logger.debug("Connected.")

            # ssh into the running interactive node
            if not self.ssh_into_interactive_node(self._second_ssh, jp_interactive_host):
                return False
            self._second_ssh.logfile_read = STDOUT_BUFFER  # print any errors/output from self._second_ssh to stdout

        # password is not needed anymore
        self.clear_pass()

        print("\nJupyter is ready! Access at:\n{}".format(jp_site))

        # open Jupyter in browser
        if not self.no_browser:
            self.logger.info("Opening in browser...")
            if not self.open_in_browser(jp_site):
                self.logger.error("Please open the Jupyter page manually.")

        # quit XQuartz because the application is not necessary to keep the connection open.
        if not self.keep_xquartz:
            try_quit_xquartz()

        return True

    def start_jupyter(self, s):
        """Start Jupyter in the given CustomSSH instance
        :param s: an active CustomSSH
        :return: the site where Jupyter can be accessed
        """
        # start jupyter
        self.logger.info("Starting Jupyter {}.".format(self.subcommand))
        for command in self.init_jupyter_commands:
            s.sendlineprompt(command, silence=False, check_exit_status=True)
        s.sendline(self.jp_call, silence=False)
        s.logfile_read = STDOUT_BUFFER

        # get the address jupyter is running at
        site_pat = re.compile(JP_SITE_PATTERN_FORMAT.format(port=self.jp_port).encode('utf-8'))
        prompt = s.PROMPT
        s.PROMPT = site_pat
        if not s.prompt():  # timed out; failed to launch jupyter
            self.logger.error("Failed to launch jupyter. (timed out, {})".format(s.timeout))
            return False
        s.PROMPT = prompt
        jp_site = s.after.decode('utf-8').strip()
        self.logger.debug("Jupyter {} started.".format(self.subcommand))

        return jp_site

    def start_interactive_session(self, s, sendpass=False):
        """Start an interactive session in the given CustomSSH instance

        :param s: an active CustomSSH
        :param sendpass: when connecting, wait for password request and then send password
        :return: the name of the interactive node, or False on failure
        """
        # enter an interactive session
        self.logger.info("Starting an interactive session.")
        if self.logger.isEnabledFor(logging.DEBUG):
            s.logfile_read = STDOUT_BUFFER
        else:
            s.logfile_read = FilteredOut(
                STDOUT_BUFFER, [b'srun:', b'authenticity'], reactions={b'authenticity': self.close_on_known_hosts_error}
            )

        timeout = s.timeout if self.srun_timeout == -1 else self.srun_timeout
        if sendpass:
            s.PROMPT = self.password_request_pattern
            if not s.sendlineprompt(self.srun_call, silence=False, timeout=self.srun_timeout)[1]:
                self.logger.error("The timeout ({}) was reached without receiving a password request.".format(timeout))
                return False
            s.sendpass(self.__pass)  # automatically silences all logfiles in s
        else:
            s.PROMPT = "\$"
            if not s.sendlineprompt(self.srun_call, silence=False, timeout=self.srun_timeout)[1]:
                self.logger.error("The timeout ({}) was reached without receiving a prompt.".format(timeout))
                return False
            s.logfile_read = None

        # within interactive session: get the name of the interactive node
        s.PROMPT = s.UNIQUE_PROMPT
        s.sendlineprompt("unset PROMPT_COMMAND; PS1='[PEXPECT]\$ '")
        jp_interactive_host = s.get_hostname().split('.')[0]
        self.logger.debug("Interactive session started.")
        self.logger.info("Node: {}\n".format(jp_interactive_host))

        return jp_interactive_host

    def close_on_known_hosts_error(self):
        self.logger.critical("\nCould not connect to interactive session.\n"
                             "For some reason, the requested node is not recognized in ssh_known_hosts.\n"
                             "If on O2, check with HMS RC.")
        self.term()
    
    def ssh_into_interactive_node(self, s, interactive_host, sendpass=False):
        """SSH into an interactive node from within the server and forward its connection

        :param s: an active CustomSSH
        :param interactive_host: the name of the interactive node
        :param sendpass: when connecting, wait for password request and then send password
        :return: True if the connection is successful
        """
        self.logger.info("Connecting to the interactive node.")
        jp_interactive_command = "ssh -N -L {0}:127.0.0.1:{0} {1}".format(self.jp_port, interactive_host)

        if sendpass:
            prompt = s.PROMPT
            s.PROMPT = self.password_request_pattern
            if not s.sendlineprompt(jp_interactive_command, silence=False)[1]:
                self.logger.error("The timeout ({}) was reached.".format(s.timeout))
                return False
            s.PROMPT = prompt
            s.sendpass(self.__pass)
        else:
            s.sendline(jp_interactive_command, silence=False)

        self.logger.debug("Connected.")
        return True

    def open_in_browser(self, site):
        try:
            webbrowser.open(site, new=2)
        except webbrowser.Error as error:
            self.logger.error("Error: {}".format(error))
            return False
        return True

    def interact(self):
        """Keep the ssh session alive and allow input such as Ctrl-C to close Jupyter."""
        self._login_ssh.silence_logs()
        if self.keep_alive:  # exit when you log out of the login shell
            interact_filter = FilteredOut(None, b'[PEXPECT]$ logout')
            self._login_ssh.interact(output_filter=interact_filter.exit_on_find)
        else:  # exit when jupyter exits and [PEXPECT]$ appears
            interact_filter = FilteredOut(None, b'[PEXPECT]$ ')
            self._login_ssh.interact(output_filter=interact_filter.exit_on_find)

    def clear_pass(self):
        cleared = zero(self.__pass)
        self.__pass = None
        return cleared

    def close(self, print_func=print, *__):
        """Close JupyterRemote.
        Print messages if used in logging.DEBUG mode.
        :param print_func: the function to use to print, allows printing to be disabled if necessary,
        using `print_func=lambda x, end=None, flush=None: None`.
        """
        def _print(*args, **kwargs):
            if sys.version_info[:2] < (3, 3):
                kwargs.pop('flush', None)
            if self.logger.isEnabledFor(logging.DEBUG):
                print_func(*args, **kwargs)
        _print("Cleaning up\r\n", end="", flush=True)
        self.clear_pass()
        self._pinentry.close()
        if not self._login_ssh.closed:
            _print("Closing login_ssh\n", end="", flush=True)
            self._login_ssh.close(force=True)
        if not self._second_ssh.closed:
            _print("Closing second_ssh\n", end="", flush=True)
            self._second_ssh.close(force=True)

    def term(self, *__):
        """Terminate JupyterRemote and exit."""
        if not self.flag_exit:
            self.flag_exit = True
            try:
                self.close()
            except RuntimeError:  # printing from signal can cause RuntimeError: reentrant call
                self.close(print_func=lambda x, end=None, flush=None: None)
            sys.stdout.close()
            sys.stderr.close()
            sys.stdin.close()
            os.closerange(0, 3)
            os._exit(1)


def main():
    # load the config file
    config_mgr = ConfigManager()
    cfg_locations = config_mgr.cfg_locations

    # get the server profile
    pargs = vars(get_base_arg_parser().parse_args())
    profile = pargs.get("profile", None)
    subcommand = None
    if profile:
        read_profile = config_mgr.read_profile(profile)
        if not read_profile:
            # no config files found for this profile, so use it as a subcommand
            subcommand = profile

    # parse the command line arguments, incorporating the complete set of defaults
    pargs = vars(config_mgr.get_arg_parser().parse_args())
    pargs.pop('profile')
    if subcommand is not None:
        pargs['subcommand'] = subcommand

    # print the current version and exit
    if pargs.pop('version'):
        print(__version__)
        return 0

    # generate the config file and exit
    gen_config = pargs.pop('generate_config')
    if gen_config:
        cfg_path = generate_config_file(gen_config)
        print('Generated config file at:\n    {}'.format(cfg_path))
        return 0

    # print the paths where config files are located, in descending order of precedence, and exit
    if pargs.pop('paths'):
        print('\n    '.join(["Searching for config file in:"] + CFG_SEARCH_LOCATIONS[::-1]))
        print('\n    '.join(["Found config file in:"] + cfg_locations[::-1]))
        return 0

    # configure the logging level
    logging.basicConfig(level=logging.INFO, format="%(msg)s")
    if pargs.pop('verbose'):
        logging.getLogger().setLevel(logging.DEBUG)  # set root logger level

    logger = logging.getLogger(__name__)

    if not cfg_locations:
        logger.warning("Config file could not be read. Using internal defaults.")
    else:
        logger.debug("Config file(s) read from (in decreasing priority):\n{}\n"
                     .format('\n'.join(cfg_locations[::-1])))

    if not pargs['subcommand']:
        default_jp_subcommand = config_mgr.config.get('Defaults', 'DEFAULT_JP_SUBCOMMAND')
        # # removed error message so that program will use the default subcommand
        # JRMT_ARG_PARSER.error("the following arguments are required: subcommand")
        logger.warning("Jupyter subcommand not provided. Using default: {}".format(default_jp_subcommand))
        pargs['subcommand'] = default_jp_subcommand

    # start Jupyter-Remote
    print_pargs = {i: pargs[i] for i in pargs if i not in ["keepxquartz", "forcegetpass", "forwardx11trusted"]}
    logger.debug(
        "\n    ".join(
            ["Running Jupyter-Remote with options:"] +
            [
                " " * (max(map(len, print_pargs.keys())) - len(pair[0])) +
                ": ".join(str(item) for item in pair)
                for pair in print_pargs.items()
            ]
        ) +
        "\n"
    )
    try:
        jupyter_rmt_runner = JupyterRemote(config_mgr.config, **pargs)
        jupyter_rmt_runner.run()
    except JupyterRemoteException as err:
        logger.error("{0}: {1}".format(err.__class__.__name__, err))
        return 1

    return 0
