#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import sys
from shutil import rmtree
from tempfile import mkdtemp, mkstemp
from unittest import TestCase, main

if sys.version_info[0] == 3:
    from io import StringIO
else:
    from StringIO import StringIO

import gnupg
import pyperclip

import passtis

# XXX: ugly hack to support GnuPG 2.1 KEY_CONSIDERED, until python-gnupg does a new release
old_handle_status = gnupg.ImportResult.handle_status
def fixed_handle_status(self, key, value):
    if key != 'KEY_CONSIDERED':
        old_handle_status(self, key, value)
gnupg.ImportResult.handle_status = fixed_handle_status
# XXX: end of ugly fix

GPG_KEY = """-----BEGIN PGP PRIVATE KEY BLOCK-----

lQOYBFhPWbABCACv2PooI2iiSkSNtcJMcj6+ABGqGW0qXwx7O759GkbaX3D/wP8F
ySg8UkgvcnpAt4xNvj1WdFMIAQLyL7tsC584m9xIcOu2aKq/T1F7f6JO5YMdGQGv
l+5mzgQiuSm3HX3mEitaUDpbgA7HjBep5BeKpbb/cD7EhEnag/EIECDxJ6WFLfOz
ZY35pVpnvxoM9oa9OWboWgQcT1eQNjnJTpp88cN5EoPBY7KwPYjECds9BfIfu8AS
BWvWPOqEqoQGMIeXbP39LtsWhbDagTHmlgOajOCE7cnOObCr+5qp/Aj0yGcfVHjO
fj79cEir9EPXf4qjOjyJAbCsIslKHPQn25QHABEBAAEAB/9MB3y1QQX68TBtstHk
upqNDLuWd3LfGIRtfbnRHjzXKt/Q/HFm33/RgOPr+8uG0rVLYb7kc9v4gHN1IhUf
VHENiTn3ajdHwT5eA93fjyIuiYYkXQ0BDigJ8/YOy08ReKNYB7AN1tU8fYQmW9hZ
YKCbFiYmkDHbRrUl0Nk0WsDbcshVE4DNc0oZ26XEFj2uhXSLn3YWMXBXTeDP76Z8
6RdFRZnkvEC2A/CycV/2Em11MTwvlIkwd8lwK9OXbMp8qzPhN6kXWwqvloJ5jwwP
UPjAnqwdDvEsZ6Vhl6kXMGITiZXOPamb1RgQqi+us4QuYKSbMa9YBMA4amsQQIHZ
8xodBADEYQgY2omhoWOmlQ5jQAxFNHMF9zKkEJagJdRXm0majB3tAM3diBZ+AGZ0
nzvfn7DqQQo2Xe8SNvgHJ/hDAaWif7p4qTdPaphTIsjT6mjmjjSqzEBv9jXGW0vH
xJvaO507bdcgCxtajMco4ffAS+GjgA8geRl/o314EOxWqgaTVQQA5TwzEIbQpJ9J
+h1X2OdZXOm2LYCJiSxyigSyv5hBuD5M5TvbYhPyV8dAr14l89knLT0aZUV6FFO9
75aRilxroVVxqJp8QScrxaRfVH2tjaQhj9uIOu3Eihupj6lubXzHpsOmRAwDfgxw
ARhPYVrZf/IThRnihlGk5JE0UYZDAesD/2kWJ8Hb9bpMJxNteW5CVJKUzYPoM8Xr
sH96+Yrkl1wntzsFie7yRd7B2F1ImhlrSF/NqrfLjCcabjOFjctZiRD+Av0E6rfK
ONY5yRuz08v6Rzf5EEPGhN3QWkokASPTp9itIGsK9lAQc681PNs+ZxvcbXcjDIjH
QU50hs8HPquHM2C0KEF1dG9nZW5lcmF0ZWQgS2V5IDxtYXR0b3Vmb3V0dUBzaGVy
bG9jaz6JATcEEwEIACEFAlhPWbACGy8FCwkIBwIGFQgJCgsCBBYCAwECHgECF4AA
CgkQ/TGHU7AzbHsiKwf7Bms2LlhKjwIRFJk7YJgEdXisiMbYs2LV93ZOUJIimq88
sPulmZYNeh/Gm0m3zhfARo8G6S3PeaeB7MEQcdSWEjnvZ6S5qCEk2E7Opq5G/lk4
IAmqkgPYCk2K6JFNq7G0BvvdsLNSNKBLnHTP9y4QCuNmb529tklsHiiakzvH1ZSd
ShV9U01QSvF3BzJB5t4HiR90cnhz5qO8gNmk88v0mbESSdOKaP2ddJZQcMKcOhAI
tK9yuFpvhr4O0zocupYaYbeDUmtB+/ZVJBcVKgMPhS5aJEmimmIr5LnyYQjhiFEp
A96AzzpfxRslYqYOlmT1eNKTHS4TMZuRju9JksEz2w==
=9yaU
-----END PGP PRIVATE KEY BLOCK-----
"""
GPG_KEY_TRUST = '5292CCC3690AB5714DA4769EFD318753B0336C7B:6:\n'


class MockedArgs(object):
    dir = None
    key_id = None
    name = 'testsite'
    user = 'testuser'
    uri = 'http://example.com'
    comment = 'such password, very secure'
    group = 'default'
    generate = True
    yes = True
    groups = ['testgroup', 'testgroup2', 'NoSuchGroup']
    echo = True
    silent = False
    verbose = False


class PasstisTestCase(TestCase):
    gpg_home = mkdtemp(suffix='-passtis-gpg')
    gpg = gnupg.GPG(gnupghome=gpg_home)
    gpg_passwd = 'passtis-test'
    gpg_trust_fd, gpg_trust_path = mkstemp(suffix='-passtis-gpg-trust')
    passwd_re = re.compile(r'Password : ([{}]{{{:d}}})'.format(
        re.escape(''.join(passtis.PASSWORD_CHARSETS.values())),
        sum(passtis.PASSWORD_DISTRIBUTION.values())
    ))

    @classmethod
    def setUpClass(cls):
        passtis.TESTING = True
        cls.gpg.import_keys(GPG_KEY)
        keys = cls.gpg.list_keys()
        MockedArgs.key_id = keys[-1]['keyid']
        # another ugly hack, as python-gnupg doesn't seem to allow changing a key's trust
        trust_file = os.fdopen(cls.gpg_trust_fd, 'w')
        trust_file.write(GPG_KEY_TRUST)
        trust_file.close()
        os.system('gpg --homedir={} --import-ownertrust < {} &>/dev/null'.format(cls.gpg_home, cls.gpg_trust_path))

    @classmethod
    def tearDownClass(cls):
        if os.path.isdir(cls.gpg_home):
            rmtree(cls.gpg_home)
        if os.path.exists(cls.gpg_trust_path):
            os.unlink(cls.gpg_trust_path)

    def setUp(self):
        self.args = MockedArgs()
        self.args.dir = mkdtemp(suffix='-passtis')
        rmtree(self.args.dir)
        self.stdout = StringIO()
        self.real_stdout = sys.stdout
        sys.stdout = self.stdout
        passtis.store_init(self.args, gnupghome=self.gpg_home)
        self.stdout.seek(0)

    def tearDown(self):
        if os.path.isdir(self.args.dir):
            rmtree(self.args.dir)
        self.stdout.close()
        sys.stdout = self.real_stdout

    def get_output(self):
        self.stdout.seek(0)
        data = self.stdout.read()
        self.stdout.seek(0)
        return data

    def test_00_clipboard(self):
        password = 'JustSomeTestPassword'
        pyperclip.copy(password)
        # check if clipboard content is good
        password2 = pyperclip.paste()
        self.assertEqual(
            password, password2,
            'returned password is not the expected one: {} != {}'.format(password, password2)
        )
        # check if content is properly cleaned when needed
        pyperclip.copy('')
        password3 = pyperclip.paste()
        self.assertNotEqual(
            password, password3,
            'pyperclip did not properly clean clipboard content'
        )

    def test_01_init(self):
        self.assertTrue(
            os.path.isdir(self.args.dir),
            'store folder was not created: {}'.format(self.args.dir)
        )
        key_id_path = os.path.join(self.args.dir, '.key-id')
        self.assertTrue(
            os.path.exists(key_id_path),
            'key id was not added to the store: {}'.format(key_id_path)
        )
        self.assertEqual(
            passtis.get_key_id(self.args.dir), self.args.key_id,
            'key id is not valid'
        )

    def test_02_add(self):
        for group in ['default'] + self.args.groups:
            self.args.group = group
            passtis.store_add(self.args, gnupghome=self.gpg_home)
            entry_path = os.path.join(self.args.dir, self.args.group, self.args.name)
            self.assertTrue(
                os.path.exists(entry_path),
                'entry file was not added to the store: {}'.format(entry_path)
            )
            self.assertTrue(
                self.passwd_re.search(self.get_output()) is not None,
                'output didn\'t contain generated password'
            )

    def test_03_del(self):
        passtis.store_add(self.args, gnupghome=self.gpg_home)
        entry_path = os.path.join(self.args.dir, self.args.group, self.args.name)
        self.assertTrue(
            os.path.exists(entry_path),
            'entry file was not added to the store: {}'.format(entry_path)
        )
        passtis.store_del(self.args)
        self.assertFalse(
            os.path.exists(entry_path),
            'test entry file was not deleted from the store: {}'.format(entry_path)
        )

    def test_04_get(self):
        passtis.store_add(self.args, gnupghome=self.gpg_home)
        out = self.get_output()
        password = self.passwd_re.search(out).group(1)
        # with echo enabled
        passtis.store_get(self.args, gnupghome=self.gpg_home)
        out = self.get_output()
        password2 = self.passwd_re.search(out).group(1)
        self.assertEqual(
            password, password2,
            'returned password is not the expected one: {} != {}'.format(password, password2)
        )
        # with echo disabled
        self.args.echo = False
        passtis.store_get(self.args, gnupghome=self.gpg_home)
        out = self.get_output()
        self.assertTrue(
            self.passwd_re.search(out) is None,
            'password was echoed-out while it shouldn\'t have'
        )

    def test_05_list(self):
        for group in ['default'] + self.args.groups:
            self.args.group = group
            passtis.store_add(self.args, gnupghome=self.gpg_home)
        self.get_output()  # clean output buffer
        passtis.store_list(self.args)
        out = self.get_output()
        for group in self.args.groups:
            self.assertTrue(
                group in out,
                'inserted group was not present in output: {}'.format(group)
            )
        self.assertFalse(
            'default' in out,
            'default group should not appear when filtering groups'
        )

    def test_06_edit(self):
        passtis.store_add(self.args, gnupghome=self.gpg_home)
        out = self.get_output()
        password = self.passwd_re.search(out).group(1)
        passtis.store_edit(self.args, gnupghome=self.gpg_home)
        out = self.get_output()
        password2 = self.passwd_re.search(out).group(1)
        self.assertNotEqual(
            password, password2,
            'password was not modified: {} == {}'.format(password, password2)
        )


if __name__ == '__main__':
    main()
