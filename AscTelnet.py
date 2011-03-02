
import socket
import select
import sys
import time

from AscUtil import no_op, hex_to_ascii

SE = chr(240)
SB = chr(250)
WILL = chr(251)
WONT = chr(252)
DO = chr(253)
DONT = chr(254)
IAC = chr(255)

STATE_WANT_TO_SEND_DATA = 0
STATE_WAITING_FOR_DATA = 1
STATE_WANT_TO_SEND_PING = 2
STATE_WAITING_FOR_DATA_AND_PONG = 3

logfile = open("binary.log", "wb")

def get_telnet_command(msg):
    """
    When the telnet command starts with an escape character,
    find the command it represents if possible.
    """
    if not msg.startswith(IAC):
        return ''
    if len(msg) == 1:
        return ''
    if msg.startswith(IAC + SB):
        end_index = msg.find(IAC + SE)
        if end_index < 0:
            return ''
        return msg[:end_index+2]
    elif len(msg) == 2:
        return ''
    else:
        return msg[:3]


class Telnet:
    def __init__(self):
        self.network_state = STATE_WAITING_FOR_DATA
        self.log = open('telnet.log', 'ab')
        self.inbuffer = ''
        self.inbuffer_ansi = ''
        self.outbuffer = ''
        self.user_command = ''
        self.listeners = []
        self.custom_action = no_op
        self.npings = 0
        self.npongs = 0

    def transition(self, new_state):
        print >> self.log, self.network_state, '->', new_state
        self.log.flush()
        self.network_state = new_state
    
    def get_ping_count(self):
        return self.npings

    def get_pong_count(self):
        return self.npongs

    def get_network_state(self):
        return self.network_state

    def add_listener(self, listener):
        self.listeners.append(listener)

    def set_custom_action(self, action):
        self.custom_action = action

    def add_bot_command(self, msg):
        self.outbuffer += msg

    def add_user_command(self, msg):
        self.user_command += msg
        commands = self.user_command.split('\x0a')
        for cmd in commands[:-1]:
            if cmd:
                if cmd == 'x':
                    self.custom_action()
                else:
                    self.outbuffer += cmd
            else:
                self.outbuffer += '\n'
        self.user_command = commands[-1]

    def process_incoming_control_subcommand(self, msg):
        print >> self.log, 'subcommand:', hex_to_ascii(msg)

    def process_incoming_normal(self, msg):
        assert msg
        self.inbuffer_ansi += msg
        if self.network_state == STATE_WAITING_FOR_DATA:
            self.transition(STATE_WANT_TO_SEND_PING)

    def process_incoming_control(self, msg):
        print >> self.log, 'control sequence:', hex_to_ascii(msg)
        ctrl_io = {
            IAC + DO   + '\x18' : IAC + WILL + '\x18' + IAC + SB + '\x18\x00' + 'xterm-color' + IAC + SE,
            IAC + DO   + '\x20' : IAC + WONT + '\x20',
            IAC + DO   + '\x23' : IAC + WONT + '\x23',
            IAC + DO   + '\x27' : IAC + WONT + '\x27',
            IAC + WILL + '\x03' : IAC + DO   + '\x03',
            IAC + DO   + '\x01' : IAC + WILL + '\x01',
            IAC + DO   + '\x1f' : IAC + WILL + '\x1f' + IAC + SB + '\x1f\x00\xa0\x00\x30' + IAC + SE,
            IAC + WILL + '\x05' : IAC + DONT + '\x05',
            IAC + DO   + '\x21' : IAC + WONT + '\x21',
            IAC + WILL + '\x01' : IAC + DONT + '\x01',
            IAC + DONT + '\x01' : IAC + WONT + '\x01'
        }
        if msg == IAC + WONT + '\x63':
            assert self.network_state == STATE_WAITING_FOR_DATA_AND_PONG
            self.npongs += 1
            self.transition(STATE_WANT_TO_SEND_DATA)
            if self.inbuffer_ansi:
                sys.stdout.write(self.inbuffer_ansi)
                sys.stdout.flush()
                for listener in self.listeners:
                    listener.process_incoming(self.inbuffer_ansi)
            else:
                print >> self.log, 'ERROR: received a pong but no ansi buffer'
            self.inbuffer_ansi = ''
        elif msg in ctrl_io:
            response = ctrl_io[msg]
            self.outbuffer += response
            if self.network_state == STATE_WAITING_FOR_DATA:
                self.transition(STATE_WANT_TO_SEND_PING)
        else:
            print >> self.log, 'I do not know how to respond to the telnet sequence.'

    def process_incoming(self, msg):
        #print >> self.log, '%s: received %d bytes' % (time.asctime(), len(msg))
        print >> self.log, len(msg)
        logfile.write(msg)
        logfile.flush()
        self.inbuffer += msg
        while True:
            index = self.inbuffer.find(IAC)
            if index == 0:
                command = get_telnet_command(self.inbuffer)
                if command.startswith(IAC + SB):
                    self.process_incoming_control_subcommand(command)
                else:
                    self.process_incoming_control(command)
                self.inbuffer = self.inbuffer[len(command):]
            elif index > 0:
                self.process_incoming_normal(self.inbuffer[:index])
                self.inbuffer = self.inbuffer[index:]
            else:
                if self.inbuffer:
                    self.process_incoming_normal(self.inbuffer)
                self.inbuffer = ''
                break

    def get_pending_output(self):
        if self.network_state == STATE_WANT_TO_SEND_PING:
            invalid_request_as_ping = IAC + DO + '\x63'
            return invalid_request_as_ping 
        elif self.network_state == STATE_WANT_TO_SEND_DATA:
            return self.outbuffer
        else:
            return None

    def notify_bytes_sent(self, nsent):
        if self.network_state == STATE_WANT_TO_SEND_PING:
            assert nsent == 3
            self.npings += 1
            self.transition(STATE_WAITING_FOR_DATA_AND_PONG)
        elif self.network_state == STATE_WANT_TO_SEND_DATA:
            self.outbuffer = self.outbuffer[nsent:]
            if not self.outbuffer:
                self.transition(STATE_WAITING_FOR_DATA)
        else:
            assert False



