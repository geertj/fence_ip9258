#!/usr/bin/env python
#
# Fencing driver for the IP Power 9258 remote power switch.

import sys
import httplib
import time

from httplib import HTTPConnection
from optparse import OptionParser


def set_port(opts, port, on):
    """Enable or disable a port on the IP9258."""
    conn = HTTPConnection(opts.ipaddr)
    headers = {}
    creds = '%s:%s' % (opts.login, opts.passwd)
    headers['Authorization'] = 'Basic %s' % creds.encode('base64')
    url = '/Set.cmd?CMD=SetPower+P%d=%d' % (59 + opts.outlet, bool(on))
    conn.request('GET', url, headers=headers)
    response = conn.getresponse()
    return response.status == httplib.OK


parser = OptionParser()
parser.add_option('-a', '--ip-address', dest='ipaddr')
parser.add_option('-l', '--login', dest='login', default='admin')
parser.add_option('-p', '--passwd', dest='passwd')
parser.add_option('-n', '--outlet', dest='outlet', type='int')
parser.add_option('-o', '--action', dest='action', type='choice',
		  choices=('reboot', 'on', 'off'), default='reboot')
parser.add_option('-r', '--reboot-delay', type='int', dest='delay', default=3)
opts, args = parser.parse_args()

if not opts.ipaddr:
    parser.error('missing required argument -a IPADDR')
if not opts.passwd:
    parser.error('missing required argument -p PASSWD')
if not opts.outlet:
    parser.error('missing required argument -n OUTLET')
if not 1 <= opts.outlet <= 4:
    parser.error('illegal port: %s' % opts.outlet)

if opts.action == 'on':
    success = set_port(opts, opts.outlet, True)
elif opts.action == 'off':
    success = set_port(opts, opts.outlet, False)
elif opts.action == 'reboot':
    success = set_port(opts, opts.outlet, False)
    if success:
        time.sleep(opts.delay)
        success = set_port(opts, opts.outlet, True)

sys.exit(success == 0)
