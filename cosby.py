#!/usr/bin/env python
"""
Connect to nethack.alt.org
and farm some puddings
"""


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



def get_screenshot():
    f = open('screenshot.txt', 'wt')
    print >> f, ansi.to_ansi_string()


class Cosby():
    def __init__(self):
        self.slaves = []
    
    def process_incoming(self, msg):
        pprint(msg)

    def add_slave(self, slave):
        self.slaves.append(slave)

coslog = open('cosby.log', 'a')

def cosby_log(msg, var=None):
    logline = time.asctime() + ": " + msg + " " + pformat(var)
    print >> coslog, logline

def main():
    """
    # farm puddings
    """
    while True:
        syslog = open('sys.log', 'a')
        print >> syslog, 'init'
        # create the socket layer
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("nethack.alt.org", 23))
        # create the telnet layer
        telnet = Telnet()
        telnet.set_custom_action(get_screenshot)
        cosby = Cosby()
        telnet.add_listener(cosby)
        cosby.add_slave(telnet)
        
        
        # alternate sending and receiving data until the connection breaks
        while True:
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
                    cosby_log("nsent", nsent)
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
                        data = sock.recv(4096)
                        cosby_log("data 2", data)
                    except sock.error, e:
                        cosby_log("socket error", e)
                        break
                    if data:
                        telnet.process_incoming(data)
                    else:
                        cosby_log('received zero bytes somehow')
                else:
                    cosby_log('timout in network state', telnet.network_state)

if __name__ == '__main__':
    #profile.run('main()')
    main()


