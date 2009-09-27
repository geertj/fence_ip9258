#!/usr/bin/env python
#
# Fencing driver for the IP Power 9258 remote power switch.

import re
import sys
import httplib
import time

from datetime import datetime, timedelta
from httplib import HTTPConnection
from optparse import OptionParser


re_html = re.compile('<.*?>')


class Error(Exception):
    """Fencing error."""


class Options(object):
    """Class to store command-line options."""
    ipaddr = None
    login = 'admin'
    passwd = None
    port = None
    option = 'reboot'
    delay = 3
    debug = False


def ip9258_rpc(opts, cmd, args=[]):
    """Execute a remote procedure call on the IP9258. Returns the HTTP
    response object.
    """
    # The IP9258 requires the URL arguments to be in a specified order.
    conn = HTTPConnection(opts.ipaddr)
    headers = {}
    creds = '%s:%s' % (opts.login, opts.passwd)
    headers['Authorization'] = 'Basic %s' % creds.encode('base64')
    url = '/Set.cmd?CMD=%s' % cmd
    url += ''.join(['+%s=%s' % (k, v) for k,v in args ])
    conn.request('GET', url, headers=headers)
    return conn.getresponse()


def set_power(opts, port, enable):
    """Set power on port `port' to `enable'."""
    args = []
    args.append(('P%d' % (59 + port), '%d' % bool(enable)))
    response = ip9258_rpc(opts, 'SetPower', args)
    if response.status != httplib.OK:
        m = '"SetPower" RPC returned status %d.' % response.status
        raise Error, m


def get_power(opts, port):
    """Get power status of port `port'."""
    response = ip9258_rpc(opts, 'GetPower')
    if response.status != httplib.OK:
        m = '"GetPower" RPC returned status %d.' % response.status
        raise Error, m
    html = response.read()
    text = re_html.sub('', html)
    try:
        tuples = [ s.split('=') for s in text.split(',') ]
        status = dict(((int(t[0][1:]) - 59, bool(int(t[1]))) for t in tuples))
    except ValueError:
        m = 'Could not parse output of "GetPower" RPC.'
        raise Error, m
    return status[port]


def reboot(opts, port):
    """Reboot the port `port'."""
    # Reboot is a power off + power on. But as we may be fencing
    # ourselves, we need to schedule the power on event as we may not be
    # there anymore.
    response = ip9258_rpc(opts, 'GetTime')
    html = response.read()
    text = re_html.sub('', html).strip()
    try:
        dt = datetime.strptime(text, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        m = 'Could not parse output of "GetTime" RPC.'
        raise Error, m
    dt += timedelta(seconds=10 + opts.delay)  # add 10 secs for safety
    args = []
    args.append(('Power', '%dA' % port))
    args.append(('YY', '%04d' % dt.year))
    args.append(('MM', '%02d' % dt.month))
    args.append(('DD', '%02d' % dt.day))
    args.append(('HH', '%02d' % dt.hour))
    args.append(('MN', '%02d' % dt.minute))
    args.append(('SS', '%02d' % dt.second))
    args.append(('PARAM', '128'))  # 128 means one shot
    args.append(('ONOFF', '1'))
    response = ip9258_rpc(opts, 'SetSchedule', args)
    if response.status != httplib.OK:
        m = '"SetSchedule" RPC returnd status %d.' % response.status
        raise Error, m
    set_power(opts, port, False)


# We need to support two modes of argument passing. The first one is
# with regular command-line options, the second is reading key=value
# pairs from standard input. The latter style is used by fence deamon.

if len(sys.argv) > 1:
    parser = OptionParser()
    parser.add_option('-a', '--ip-address', dest='ipaddr')
    parser.add_option('-l', '--login', dest='login', default=Options.login)
    parser.add_option('-p', '--passwd', dest='passwd')
    parser.add_option('-n', '--outlet', dest='port', type='int')
    parser.add_option('-o', '--action', dest='option', default=Options.option)
    parser.add_option('-r', '--reboot-delay', dest='delay', default=Options.delay)
    parser.add_option('-d', '--debug', dest='debug', action='store_true')
    opts, args = parser.parse_args()
else:
    opts = Options()
    for line in sys.stdin:
        key, value = line.strip().split('=')
        if key in ('port', 'debug'):
            value = int(value)
        setattr(opts, key, value)
    args = {}

if not opts.ipaddr:
    sys.stderr.write('missing required argument: IPADDR\n')
    sys.exit(1)
if not opts.passwd:
    sys.stderr.write('missing required argument: PASSWD\n')
    sys.exit(1)
if not opts.port:
    sys.stderr.write('missing required argument: PORT\n')
    sys.exit(1)
if not 1 <= opts.port <= 8:
    sys.stderr.write('illegal port: %d\n' % opts.port)
    sys.exit(1)
if opts.option not in ('on', 'off', 'reboot', 'status'):
    sys.stderr.write('illegal action: %s\n' % opts.option)
    sys.exit(1)

if opts.debug:
    for var in ('ipaddr', 'login', 'passwd', 'port', 'option', 'debug'):
        print '%s: %s' % (var.upper(), getattr(opts, var))

command = opts.option
port = opts.port
status = get_power(opts, port)

try:
    if command == 'on':
        if status:
            print 'Success: Already ON'
        else:
            set_power(opts, port, 1)
            print 'Success: Powered ON'
    elif command == 'off':
        if status:
            set_power(opts, port, 0)
            print 'Success: Powered OFF'
        else:
            print 'Success: Already OFF'
    elif command == 'reboot':
        reboot(opts, port)
        print 'Success: Powered OFF and scheduled power ON'
    elif command == 'status':
        print 'Status: %s' % (status and 'ON' of 'OFF')

except (Error, httplib.HTTPException), exc:
    if opts.debug:
        raise
    sys.stderr.write('An uncaught exception occurred. Try --debug.\n')
    sys.exit(1)
