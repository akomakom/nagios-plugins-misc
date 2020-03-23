#!/usr/bin/env python3

###############################################################################################
# Nagios check for listening ports
#   Verifies that the host (local or remote) is listening on the expected ports.
#   Can check for:
#     * No unexpected listening ports
#     * All expected ports are listening
#   Optional ports are effectively ignored.
#
# Examples:
#
#  * Check TCP ports on localhost (8080 is optional, down is OK):
#     -t 80,443 -T 8080
#
#  * Same on remote host
#     -H remote_host -t 80,443 -T 8080
#
#  * UDP also (-U is optional)
#     -H remote_host -t 80,443 -T 8080 -u 999 -U 500,1000-2000
#
#  * Customizing ssh
#     -H remote_host --sshcmd 'ssh -i /some/key -X -oStrictHostKeyChecking=false' ...
#
###############################################################################################

from subprocess import PIPE,Popen
import argparse

parser = argparse.ArgumentParser(description='Check for correct listening ports on a remote machine.  '
                                             '\nPorts can be specified as ranges, ie 80,443,8000-8100,10000 ')
parser.add_argument('-H', dest='host', help='host for ssh (runs on localhost otherwise)')
parser.add_argument('--sshcmd', help='SSH command and optional args', default='ssh')
parser.add_argument('-t', help='list of required TCP ports or ranges, comma-delimited', default='')
parser.add_argument('-T', help='list of optional TCP ports or ranges, comma-delimited', default='')
parser.add_argument('-u', help='list of required UDP ports or ranges, comma-delimited', default='')
parser.add_argument('-U', help='list of optional UDP ports or ranges, comma-delimited', default='')
parser.add_argument('-d', help='Debug output', default=False, action='store_true')

args = None # later



output = []

def debug(string):
    if args.d:
        print("DEBUG: %s " % string)

# breaks up a string like 1,4,5-10,300 (etc)
def parse_ports(spec):
    debug("Parsing port spec: '%s'" % spec)
    result = []
    for part in spec.split(','):
        if '-' in part:
            a, b = part.split('-')
            a, b = int(a), int(b)
            result.extend(range(a, b + 1))
        elif part != '':
            a = int(part)
            result.append(a)
    debug("Result: '%s'" % result)
    return result

def get_ports(args, type):
    if args.host:
        command = "%s %s \"netstat -nl%s | grep -v 127.0.0.1 | grep : | sed 's/.*:\([0-9]*\) .*$/\\1/' | sort -nu | xargs\"" % (args.sshcmd, args.host, type)
    else:
        command = "netstat -nl%s | grep -v 127.0.0.1 | grep : | sed 's/.*:\([0-9]*\) .*$/\\1/' | sort -nu | xargs" % type

    debug("Running command '%s'" % command)
    p = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = p.communicate()
    if p.returncode == 0:
        command_output = stdout.strip().split()
    else:
        # error running
        raise OSError("Unable to run command[code %s]: %s" % (p.returncode, stderr.strip()))

    debug("Command '%s' output is '%s'/'%s'" % (command, stdout, stderr))
    return list(map(int, command_output)) #convert to ints


def compare(actual, required, optional, description):
    missing = (list(set(required) - set(actual)))
    extras = (list(set(actual) - set(required) - set(optional)))
    ok = ((len(missing) + len(extras)) == 0)

    if not ok:
        output.append("Incorrect %s listening ports" % description)
        debug("Expected %s [%s] but got %s.  " % (required, optional, actual))

    if len(missing) > 0:
        output.append("Missing: %s" % missing)
    if len(extras) > 0:
        output.append("Unexpected: %s" % extras)

    if ok:
        output.append("%s %s" % (description, actual))

    return ok


# Begin execution
try:
    args = parser.parse_args()

    debug(args)

    tcp_ports = parse_ports(args.t)
    udp_ports = parse_ports(args.u)
    tcp_ports_opt = parse_ports(args.T)
    udp_ports_opt = parse_ports(args.U)
except SystemExit:
    exit(3)
except BaseException as err:
    print("Unable to parse arguments: %s" % err)
    exit(3)  # Unknown internal error parsing args

ok = True
try:
    if (len(tcp_ports) + len(tcp_ports_opt)) > 0:
        ok = compare(get_ports(args, 't'), tcp_ports, tcp_ports_opt, "TCP")
    if (len(udp_ports) + len(udp_ports_opt)) > 0:
        ok = ok and compare(get_ports(args, 'u'), udp_ports, udp_ports_opt, "UDP")

    if ok:
        output.insert(0, "OK")
except Exception as err:
    print("Internal error: %s" % err)
    exit(3) # unknown internal error while running command.

print('. '.join(output))

if not ok:
    exit(1) # wrong ports
