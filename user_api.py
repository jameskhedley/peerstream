#! /usr/bin/python3.6m
'''Calls allowing the implementation of a user interface controlling the
operation of Peerstream. If you want to make a web UI or something, these
are the calls you should use.'''

import stream

def is_server_running():
    return stream.is_server_running()

def start_server(port):
    return stream.run_server_proc(port)

def stop_server():
    return stream.stop_server_proc()

def peer_list():
    return stream.PEERS

def clips_list():
    return stream.SLOTS.keys()
