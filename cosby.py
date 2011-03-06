#!/usr/bin/env python
"""
Connect to nethack.alt.org
and farm some puddings
"""


from optparse import OptionParser
from cosby_log import cosby_log
import profile
import socket
import select
import sys
import time
import random
import re


from AscTelnet import Telnet
from AscTelnet import STATE_WANT_TO_SEND_DATA
from AscTelnet import STATE_WAITING_FOR_DATA
from AscTelnet import STATE_WANT_TO_SEND_PING
from AscTelnet import STATE_WAITING_FOR_DATA_AND_PONG
from pprint import pprint, pformat

class DebugStop(Exception):
    pass


def get_screenshot():
    f = open('screenshot.txt', 'wt')
    print >> f, ansi.to_ansi_string()


class Cosby():
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.slaves = []
    
    def process_incoming(self, msg):
        cosby_log("processing message: ", msg)
        if "l) Login" in msg:
            self.give_order('l')
        if "Please enter your username" in msg:
            self.give_order('Cosbytest')

    def add_slave(self, slave):
        self.slaves.append(slave)

    def give_order(self, msg):
        cosby_log("command: ", msg);
        
        cosby_log("I have %s slaves" % len(self.slaves), self.slaves)
        for slave in self.slaves:
            cosby_log('sending command to a slave', msg)
            slave.add_bot_command(msg)


def main(username, password):
    """
    # farm puddings
    """
    while True:
        cosby_log('init')
        # create the socket layer
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("nethack.alt.org", 23))
        # create the telnet layer
        telnet = Telnet()
        telnet.set_custom_action(get_screenshot)
        cosby = Cosby(username, password)
        telnet.add_listener(cosby)
        cosby.add_slave(telnet)
        
        
        # alternate sending and receiving data until the connection breaks
        while True:
            data = None
            cosby_log("data at the beginning", data)
            errors = [sock]
            readers = []
            writers = []
            if telnet.network_state in (STATE_WANT_TO_SEND_DATA, STATE_WANT_TO_SEND_PING):
                writers = [sock]
                canread, canwrite, haserr = select.select(readers, writers, errors, 10)
                if sock in haserr:
                    break
                if sock in canwrite:
                    data = telnet.get_pending_output()
                    cosby_log("data", data)
                    assert data
                    nsent = sock.send(data)
                    assert nsent
                    telnet.notify_bytes_sent(nsent)
                else:
                    cosby_log('timout in network state', telnet.network_state)
            elif telnet.network_state in (STATE_WAITING_FOR_DATA, STATE_WAITING_FOR_DATA_AND_PONG):
                readers = [sock]
                canread, canwrite, haserr = select.select(readers, writers, errors, 10)
                if sock in haserr:
                    break
                if sock in canread:
                    try:
                        cosby_log("data before sock:", data)
                        data = sock.recv(4096)
                        cosby_log("sock.recv() = ", data)
                    except sock.error, e:
                        cosby_log("socket error", e)
                        break
                    if data:
                        cosby_log("telnet.process_incoming(", data)
                        telnet.process_incoming(data)
                    else:
                        cosby_log('received zero bytes somehow')
                else:
                    cosby_log('timout in network state', telnet.network_state)

if __name__ == '__main__':
    #profile.run('main()')
    parser = OptionParser()
    parser.add_option("-u", "--user", dest="username",
                      help="who to log in as", metavar="USERNAME")
    parser.add_option("-p", "--password", dest="password",
                      help="password", metavar="PASSWORD")
    parser.add_option("-s", "--server", dest="server",
                      help="password", metavar="PASSWORD", default="nethack.alt.org")
    (options, args) = parser.parse_args()
#    parser.add_option("-q", "--quiet",
#                      action="store_false", dest="verbose", default=True,
#                      help="don't print status messages to stdout")
    
    (options, args) = parser.parse_args()
    main(options.username, options.password)


