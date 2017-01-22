#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#     Passtis, a GnuPG-based command line password vault.
#     Copyright (C) 2016  Mathieu Deous
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.

# TODO: check if clipboard is available

import json
import os
import random
import sys
from argparse import ArgumentParser
from getpass import getpass
from string import ascii_lowercase, ascii_uppercase, digits, punctuation
from time import sleep

import gnupg
import pyperclip

PASSWORD_CHARSETS = {
    'lower': ascii_lowercase,
    'upper': ascii_uppercase,
    'digit': digits,
    'special': punctuation
}
PASSWORD_DISTRIBUTION = {
    'lower': 10,
    'upper': 10,
    'digit': 5,
    'special': 5
}  # 10 + 10 + 5 + 5 = 30char

COLOR_BLUE = '\033[01;34m'
COLOR_GREEN = '\033[22;32m'
COLOR_RED = '\033[22;31m'
COLOR_RESET = '\033[0;0m'


def generate_password():
    """
    Generates a new random password.
    """
    password = []
    for char_type, count in PASSWORD_DISTRIBUTION.items():
        password.extend(random.choice(PASSWORD_CHARSETS[char_type]) for _ in range(count))
    random.shuffle(password)
    return ''.join(password)


def key_is_valid(gpg, key_id):
    """
    Checks if specified key is present and is sufficiently trusted (i.e. ultimate trust).
    """
    for key in gpg.list_keys():
        kid = key['keyid'][16-len(key_id):]
        if (kid == key_id) and (key['trust'] == 'u'):
            return True
    return False


def get_key_id(path):
    """
    Gets key ID for the store located at specified location.
    """
    key_path = os.path.join(path, '.key-id')
    if not os.path.isfile(key_path):
        print('{}Key ID file not found: {}{}'.format(COLOR_RED, key_path, COLOR_RESET))
        sys.exit(66)
    with open(key_path) as ifile:
        data = ifile.read().strip()
    return data


def check_store_dir(path):
    """
    Checks if specified store location exists and has a .key-id file.
    """
    if not os.path.exists(path):
        print('{}Store directory does not exist{}'.format(COLOR_RED, COLOR_RESET))
        sys.exit(66)
    key_path = os.path.join(path, '.key-id')
    if not os.path.exists(key_path):
        print('{}No key ID found: {}{}'.format(COLOR_RED, key_path, COLOR_RESET))
        sys.exit(66)


def check_entry_path(folder, group, name):
    entry_path = os.path.join(folder, group, name)
    if not os.path.isfile(entry_path):
        print('{}No such entry: {}/{}{}'.format(COLOR_RED, group, name, COLOR_RESET))
        sys.exit(66)
    return entry_path


def daemonize():
    """
    Do UNIX double-fork magic to daemonize current process.
    Shamelessly taken from https://github.com/serverdensity/python-daemon
    """
    try:
        pid = os.fork()
        if pid > 0:
            # exit from first parent
            sys.exit(0)
    except OSError as err:
        print('{}Unable to daemonize: {} ({}){}'.format(COLOR_RED, err.strerror, err.errno, COLOR_RESET))
        sys.exit(1)
    os.setsid()

    try:
        pid = os.fork()
        if pid > 0:
            # exit from second parent
            sys.exit(0)
    except OSError as err:
        print('{}Unable to daemonize: {} ({}){}'.format(COLOR_RED, err.strerror, err.errno, COLOR_RESET))
        sys.exit(1)


def prompt_password():
    while True:
        password = getpass('Password: ')
        password2 = getpass('Confirm password: ')
        if password == password2:
            break
        else:
            print("{}Passwords don't match!{}".format(COLOR_RED, COLOR_RESET))
    return password


def write_entry_file(data, gpg, key_id, entry_path):
    jsoned = json.dumps(data)
    gpg.encrypt(jsoned, [key_id], armor=True, output=entry_path)
    os.chmod(entry_path, 0o600)


def password_to_clipboard(password):
    pyperclip.copy(password)
    print('new password copied to clipboard (will be cleared in 30s)')
    daemonize()
    sleep(30)
    pyperclip.copy('')


def parse_args():
    """
    Handles command-line arguments parsing.
    """
    parser = ArgumentParser(
        description='Passtis - Command line password manager.',
        version='0.2'
    )
    parser.add_argument(
        '-d', '--dir',
        help='store location',
        default=os.path.join(os.path.expanduser('~'), '.passtis-store')
    )
    parser.add_argument(
        '-V', '--verbose',
        help='display GnuPG debug information',
        action='store_true'
    )

    subparsers = parser.add_subparsers(dest='command')

    init_parser = subparsers.add_parser('init', help='initialize the password store')
    init_parser.add_argument('key_id', help='ID of the key used for encrypting the store')

    add_parser = subparsers.add_parser('add', help='add a new entry')
    add_parser.add_argument('name', help='entry name')
    add_parser.add_argument(
        '-u', '--user',
        help='user name',
        default=''
    )
    add_parser.add_argument(
        '-U', '--uri',
        help='resource URI',
        default=''
    )
    add_parser.add_argument(
        '-c', '--comment',
        help='additional entry information',
        default=''
    )
    add_parser.add_argument(
        '-g', '--group',
        help='group the entry belongs to',
        default='default'
    )
    add_parser.add_argument(
        '-e', '--echo',
        help='display password instead of copying it to the clipboard',
        action='store_true'
    )
    add_parser.add_argument(
        '--generate',
        help='generate random password instead of prompting for one',
        action='store_true'
    )

    del_parser = subparsers.add_parser('del', help='delete an entry')
    del_parser.add_argument('name', help='entry name')
    del_parser.add_argument(
        '-g', '--group',
        help='group the entry belongs to',
        default='default'
    )
    del_parser.add_argument(
        '-y', '--yes',
        help='do not ask for confirmation',
        action='store_true'
    )

    list_parser = subparsers.add_parser('list', help='list store entries')
    list_parser.add_argument(
        '-G', '--groups',
        help='only display entries from given groups',
        nargs='+',
        metavar='GROUP'
    )

    get_parser = subparsers.add_parser('get', help='fetch an entry from the store')
    get_parser.add_argument('name', help='entry name')
    get_parser.add_argument(
        '-g', '--group',
        help='group the entry belongs to',
        default='default'
    )
    get_parser.add_argument(
        '-e', '--echo',
        help='display password instead of copying it to the clipboard',
        action='store_true'
    )
    get_parser.add_argument(
        '-s', '--silent',
        help='do not output anything',
        action='store_true'
    )

    edit_parser = subparsers.add_parser('edit', help='edit a store entry')
    edit_parser.add_argument('name', help='entry name')
    edit_parser.add_argument(
        '-g', '--group',
        help='group the entry belongs to',
        default='default'
    )
    edit_parser.add_argument(
        '-u', '--user',
        help='new user name',
        default=''
    )
    edit_parser.add_argument(
        '-U', '--uri',
        help='new resource URI',
        default=''
    )
    edit_parser.add_argument(
        '-c', '--comment',
        help='new additional entry information',
        default=''
    )
    edit_parser.add_argument(
        '-e', '--echo',
        help='display password instead of copying it to the clipboard',
        action='store_true'
    )
    edit_parser.add_argument(
        '--generate',
        help='generate random password instead of prompting for one',
        action='store_true'
    )

    return parser.parse_args()


def store_init(args, gnupghome=None):
    """
    Initializes Passtis store.
    """
    if os.path.exists(args.dir):
        print('{}Directory already exists: {}{}'.format(COLOR_RED, args.dir, COLOR_RESET))
        sys.exit(73)
    gpg = gnupg.GPG(verbose=args.verbose, gnupghome=gnupghome)
    if not key_is_valid(gpg, args.key_id):
        print('{}Key is unknown or not sufficiently trusted{}'.format(COLOR_RED, COLOR_RESET))
        sys.exit(1)
    key_path = os.path.join(args.dir, '.key-id')
    os.mkdir(args.dir, 0o700)
    with open(key_path, 'w') as ofile:
        ofile.write(args.key_id)
    print('New store created: {}{}{}'.format(COLOR_GREEN, args.dir, COLOR_RESET))


def store_add(args, gnupghome=None):
    """
    Adds a new entry to the store.
    """
    check_store_dir(args.dir)
    key_id = get_key_id(args.dir)
    output_dir = os.path.join(args.dir, args.group)
    if not os.path.isdir(output_dir):
        os.mkdir(output_dir, 0o700)
    output_file = os.path.join(output_dir, args.name)
    if os.path.exists(output_file):
        print('{}Entry already exists: {}/{}{}'.format(COLOR_RED, args.group, args.name, COLOR_RESET))
        sys.exit(73)

    gpg = gnupg.GPG(verbose=args.verbose, gnupghome=gnupghome)
    data = {
        'username': args.user,
        'uri': args.uri,
        'comment': args.comment
    }
    if args.generate:
        password = generate_password()
    else:
        password = prompt_password()
    data['password'] = password
    write_entry_file(data, gpg, key_id, output_file)
    if args.generate:
        if args.echo:
            print('Password : {}'.format(data['password']))
        else:
            password_to_clipboard(password)


def store_del(args):
    """
    Deletes an entry from the store.
    """
    check_store_dir(args.dir)
    entry_path = check_entry_path(args.dir, args.group, args.name)
    os.unlink(entry_path)
    print('Entry removed: {}{}/{}{}'.format(COLOR_GREEN, args.group, args.name, COLOR_RESET))


def store_list(args):
    """
    Lists stored groups and entries.
    """
    check_store_dir(args.dir)
    print('{}[{}]{}'.format(
        COLOR_GREEN,
        args.dir if args.verbose else 'Password Store',
        COLOR_RESET
    ))
    folders = [
        f for f in sorted(os.listdir(args.dir))
        if os.path.isdir(os.path.join(args.dir, f))
        and (f in args.groups if args.groups else True)
    ]
    for folder_idx, folder in enumerate(folders):
        if os.path.isdir(os.path.join(args.dir, folder)):
            print('{}{}──{} {}{}{}'.format(
                COLOR_GREEN, '└' if (folder_idx + 1 == len(folders)) else '├', COLOR_RESET,
                COLOR_BLUE, folder, COLOR_RESET
            ))
            entries = [
                e for e in sorted(os.listdir(os.path.join(args.dir, folder)))
                if os.path.isfile(os.path.join(args.dir, folder, e))
            ]
            for entry_idx, entry in enumerate(entries):
                print('{}{}   {}──{} {}'.format(
                    COLOR_GREEN,
                    ' ' if (folder_idx + 1 == len(folders)) else '│',
                    '└' if (entry_idx + 1 == len(entries)) else '├',
                    COLOR_RESET,
                    entry
                ))


def store_get(args, gnupghome=None, testing=False):
    """
    Reads an entry from the store.
    """
    check_store_dir(args.dir)
    entry_path = check_entry_path(args.dir, args.group, args.name)

    gpg = gnupg.GPG(verbose=args.verbose, gnupghome=gnupghome)
    with open(entry_path) as ifile:
        raw = gpg.decrypt_file(ifile).data
        data = json.loads(raw)
    if not args.silent:
        print('{green}{line} {blue}{group}/{name} {green}{line}{reset}'.format(
            green=COLOR_GREEN,
            blue=COLOR_BLUE,
            line='-' * 10,
            group=args.group,
            name=args.name,
            reset=COLOR_RESET
        ))
        for key in ('URI', 'Username', 'Comment'):
            if key.lower() != 'password':
                print('{}{:9}:{} {}'.format(COLOR_GREEN, key, COLOR_RESET, data[key.lower()]))
        if args.echo:
            print('Password : {}'.format(data['password']))
        print(COLOR_GREEN + '-' * (23 + len(args.group + args.name)) + COLOR_RESET)
    if not args.echo:
        if not args.silent:
            print('password copied to clipboard (will be cleared in 30s)')
        pyperclip.copy(data['password'])
        if not testing:
            daemonize()
            sleep(30)
            pyperclip.copy('')


def store_edit(args, gnupghome=None):
    """
    Edits an existing store entry.
    """
    check_store_dir(args.dir)
    key_id = get_key_id(args.dir)
    entry_path = check_entry_path(args.dir, args.group, args.name)

    gpg = gnupg.GPG(verbose=args.verbose, gnupghome=gnupghome)
    with open(entry_path) as ifile:
        raw = gpg.decrypt_file(ifile).data
        data = json.loads(raw)

    data['username'] = args.user or data['username']
    data['uri'] = args.uri or data['uri']
    data['comment'] = args.comment or data['comment']
    if args.generate:
        data['password'] = generate_password()
    else:
        data['password'] = prompt_password()

    write_entry_file(data, gpg, key_id, entry_path)
    if args.generate:
        if args.echo:
            print('Password : {}'.format(data['password']))
        else:
            password_to_clipboard(data['password'])


def main():
    """
    Application's entry-point.
    """
    commands = {
        'init': store_init,
        'add': store_add,
        'del': store_del,
        'list': store_list,
        'get': store_get,
        'edit': store_edit
    }
    args = parse_args()
    commands[args.command](args)


if __name__ == '__main__':
    main()
