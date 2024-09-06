#! /usr/bin/env python

import sys
from inspect import currentframe, getframeinfo
import random
import glob
import string
import re
import time
import os, shutil
import logging
import json
import threading
from multiprocessing import Process, Manager
from collections import deque
from flask import Flask, Response, request, send_from_directory, render_template
import cherrypy
import requests
from requests.exceptions import ConnectionError, ReadTimeout, ConnectTimeout

PLAYLIST_HEAD ='''#EXTM3U
#EXT-X-PLAYLIST-TYPE:EVENT
#EXT-X-VERSION:3
#EXT-X-MEDIA-SEQUENCE:0
#EXT-X-ALLOW-CACHE:YES
#EXT-X-TARGETDURATION:5
'''

logging.basicConfig(filename='server.log',level=logging.DEBUG)
logging.info('Server init!')

PROTO = "http://" #TODO oof
CHUNK = 10000 
MAX_CHANNELS = 10 #TODO how to clean up old channels?
CHANNELS_DIR = "channels"

try:
    os.mkdir(CHANNELS_DIR)
except FileExistsError:
    pass

#TODO handle connectivity issues, timeouts
ip_bytes = requests.get('http://whatismyip.akamai.com/').content
if os.path.exists('LOCAL'):
    MY_IP = 'localhost'
else:
    MY_IP = str(ip_bytes).lstrip("b").replace("'", "")
    logging.info("Detected IP address: %s" % MY_IP)
STREAM_RE = re.compile(".*stream(\S+)\.ts.*")

PEER_DICT_NEW = {"registered": False}

app = Flask(__name__, static_url_path='/hls', static_folder='hls')
#app = Flask(__name__)

class Stream():
    def __init__(self, slots, peers, channels):
        #slots, channels and peers are shared between processes so are really mp.manager proxies
        self.slots = slots #dict
        self.peers = peers #dict
        self.channels = channels #list

        self.port = None
        self.server_process = None
        self.input_process = None
        self.current_stream = 0
        
        #routes need object state but can't use self, so make them closures of __init__
        #TODO would pluggable views be any better?

        @app.route('/hls/player.html')
        def serve_player():
            #TODO give channel as an arg or as part of URL?
            channel = request.args.get('channel', None)
            if not channel:
                return Response(status='400 Error', response="need to give channel id", 
                                headers=[('Content-type', 'text/plain')])
            return render_template('player.html.j2', channel=channel)

        @app.route('/hls/<string:filename>.js')
        def serve_js(filename):
            print(filename)
            return send_from_directory('hls', filename+'.js')
    

        @app.route('/hls/<string:channel>/<path:path>')
        @app.route('/hls/<string:channel>/', defaults={'path': '', 'channel': ''})
        def index(channel, path):
            #TODO only allow this whole route from localhost? Separate service from p2p stuff?
            channel_path = os.path.join(CHANNELS_DIR, channel)
            if not channel or (not os.path.exists(channel_path)):
                return Response(status='404 Not Found', response="not handled", headers=[('Content-type', 'text/plain')])
            print("Found channel %s" % channel)
            match = STREAM_RE.match(path)
            if "stream.m3u8" in path:
                return self.playlist(request, channel)
            elif match:
                self.current_stream = int(match.groups()[0])
                if not self.current_stream in self.slots[channel].keys():
                    logging.warning("client requested strem %d but can't find it" % (self.current_stream))
                    return Response(status='202 Accepted', headers=[('Content-type', 'text/plain')])
                logging.info("Client requested stream %d" % self.current_stream)
                return Response(self.gen_stream(channel), mimetype='video/MP2T')
            else:
                return Response(status='404 Not Found', headers=[('Content-type', 'text/plain')])

        @app.route('/register', methods=['POST'])
        def register_peer():
            logging.debug("***request.form = %s" % str(request.form))
            peer_address = request.form['address']
            #peers_channels = json.loads(request.form['channels'])
            #logging.debug("***peers_channels = %s" % peers_channels)
            ##merge the channel lists
            #i = 0
            #while (len(self.channels) < MAX_CHANNELS) and peers_channels:
            #    if peers_channels[0] not in self.channels:
            #        self.channels.append(peers_channels[0])
            #    i+=1
            ##END
            logging.debug("***adding address %s to peers list" % peer_address)
            self.peers[peer_address] = {'registered': True}
            return Response(status='200 OK', response="OK", headers=[('Content-type', 'text/plain')])


        @app.route('/clip/<string:channel>', methods=['GET'])
        def request_clip(channel):
            logging.info("*** remote address = " + request.remote_addr)
            if mode == 'seed':
                #random here is meant to be 0.1 chance to actually serve clip
                #TODO make rate of actually serving clip depend upon load, somehow
                if random.randint(0,9) > 0 and len(self.peers) > 5:
                    #this is completely naive, doesn't check to see if peer has channel or not
                    proxy_url = random.choice(self.peers.keys())
                    logging.debug("305 returning proxy_url as %s" % proxy_url)
                    return Response(status="305 Use Proxy", response=proxy_url)
            logging.debug("request_clip: self.peers is now %s" % (str(self.peers.keys())))
            try:
                clip_int = int(request.args.get('key', ''))
            except ValueError:
                logging.error("Bad clip number")
                return Response(status='400 Error', response="clips must be an integer", 
                                headers=[('Content-type', 'text/plain')])

            requested_file = 'OUTPUT%03d.ts' % clip_int
            requested_file_path = os.path.join(CHANNELS_DIR, channel, requested_file)
            logging.debug("Request resolves to file %s" % requested_file_path)

            if os.path.exists(requested_file_path):
                with open(requested_file_path, 'rb') as hclip:
                    clip_data = hclip.read()
                return Response(status='200 OK', response=clip_data, headers=[('Content-type', 'video/MP2T')])
            else:
                logging.warning("404 on clip %d with file name %s" % (clip_int, requested_file))
                return Response(status='404 Not found', response="haven't got this clip", 
                                headers=[('Content-type', 'text/plain')])

        @app.route('/shutdown', methods=['GET'])
        def shutdown():
            shutdown_server()
            return "OK"

        @app.route('/hello', methods=['GET'])
        def hello():
            return Response(status='200 OK', response="wagwan", headers=[('Content-type', 'text/plain')])

        @app.route('/peers', methods=['GET'])
        def peers():
            data = json.dumps(self.peers.keys())
            return Response(status='200 OK', response=data, headers=[('Content-type', 'application/json')])

        @app.route('/channels', methods=['GET'])
        def channels():
            data = json.dumps(list(self.channels))
            return Response(status='200 OK', response=data, headers=[('Content-type', 'application/json')])

        @app.route('/peers_debug', methods=['GET'])
        def peers_debug():
            data = json.dumps(dict(self.peers))
            data = data + " " + str(id(self.peers))
            return Response(status='200 OK', response=data, headers=[('Content-type', 'application/json')])

    def playlist(self, request, channel):
        playlist_tail = ""
        for i in sorted(self.slots[channel].items()[:-1]):
            playlist_tail += '''#EXTINF:5,
%shls/%s/stream%d.ts
''' % (request.url_root, channel, i[0])
        playlist = PLAYLIST_HEAD + playlist_tail
        return Response(response=playlist, status='200 OK', 
                        headers=[('Content-type', 'application/x-mpegURL')])

    def gen_stream(self, channel):
        if self.slots:
            data = self.slots[channel][self.current_stream]
            while data:
                batch = data[0:CHUNK] #10K
                data = data[CHUNK:]
                yield batch
            #TODO guess this saves memory but don't know if good idea
            #self.slots[channel][self.current_stream]=None
            return
        return

    def update_peer_record(self, peer, **kwargs):
        logging.debug("Updating record for peer %s" % peer)
        for k, v in kwargs.items():
            temp_d = self.peers[peer]
            temp_d[k] = v
            self.peers[peer] = temp_d

    def channel_thread(self):
        '''scans all known peers for new channels'''
        while True:
            logging.debug("Channel thread tick")
            new_channels = []
            time.sleep(1.2)
            #ask registered peers for more connections
            for peer, vals in dict(self.peers).items():
                #TODO self.peers should never be empty, if it is then seeds are dead
                if not vals['registered']:
                    continue
                logging.info("asking peer %s for more channels" % (peer))
                channels_url = '%schannels' % (peer)
                try:
                    resp = requests.get(channels_url, timeout=3.1)
                except ConnectionError:
                    logging.warning("Channels thread: peer url %s is unreachable" % channels_url)
                except (ReadTimeout, ConnectTimeout):
                    logging.warning("Channels thread: peer %s timed out" % peer)
                else:
                    if resp.status_code == 200:
                        logging.info("Got channels list: %s" % (str(resp.content)))
                        new_channels = json.loads(resp.content)
                        for nc in new_channels:
                            if nc not in self.channels:
                                self.channels.append(nc)
                        logging.info("channels list is now: %s" % (str(self.channels)))
                    else:
                        logging.warning("Channels thread: unexpected status %d from peer %s" % (resp.status_code, peer))
            

    def peer_thread(self):
        '''keeps scanning peers for new information. 
is a member of stream because it's a thread rather than a process (WHY?)'''
        while True:
            logging.debug("Peer thread tick")
            new_peers = []
            time.sleep(1)
            #try to register with any unregistered peers
            for peer, vals in dict(self.peers).items():
                if MY_IP + ":" + str(self.arg_port) in peer:
                    #don't need to register with yourself
                    self.update_peer_record(peer, registered=True)
                    continue
                if vals['registered']:
                    continue
                logging.info("registering with peer %s" % (peer))
                register_url = '%sregister' % (peer)
                try:
                    logging.debug(register_url)
                    resp = requests.post(register_url, 
                                         #data={'address': 'http://%s:%s/' % (MY_IP, str(self.arg_port)),
                                         #      'channels': json.dumps(list(self.channels))},
                                         data={'address': 'http://%s:%s/' % (MY_IP, str(self.arg_port))},
                                         timeout=2.0)
                except ConnectionError:
                    logging.warning("register - peer %s is down" % peer)
                else:
                    if resp.status_code == 200:
                        self.update_peer_record(peer, registered=True)
                        logging.debug("Peer %s should be registered now" % peer)
                        logging.info("register - 200 OK")
                    else:
                        logging.warning("register - status code was %d" % resp.status_code)
                    #TODO interpret resp
            
            #ask registered peers for more connections
            for peer in self.peers.keys():
                #TODO self.peers should never be empty, if it is then seeds are dead
                if not vals['registered']:
                    continue
                logging.info("asking peer %s for more peers" % (peer))
                peers_url = '%speers' % (peer)
                try:
                    resp = requests.get(peers_url, timeout=3.1)
                except ConnectionError:
                    logging.warning("Peer thread: peer url %s is unreachable" % peers_url)
                    #TODO don't remove right away but could be a 3 strike system or score
                    #self.peers.pop(peer)
                except (ReadTimeout, ConnectTimeout):
                    logging.warning("Peer thread: peer %s timed out" % peer)
                else:
                    if resp.status_code == 200:
                        logging.info("Got peers list: %s" % (str(resp.content)))
                        new_peers = json.loads(resp.content)
                    else:
                        logging.warning("Peer thread: unexpected status %d from peer %s" % (resp.status_code, peer))
            for new_peer in new_peers:
                if new_peer not in self.peers:
                    self.peers[new_peer] = PEER_DICT_NEW
            logging.info("Peers list is now: %s" % (str(self.peers)))
                

    def run_server(self, port, host='0.0.0.0', processes=1, debug=False):    
        '''run using cherrypy'''
        self.arg_port = port
        cherrypy.tree.graft(app.wsgi_app, '/')
        print("GRAFT SUCCESSFUL")
        cherrypy.config.update({'server.socket_host': host,
                                'server.socket_port': port,
                                'engine.autoreload.on': False,})
        cherrypy.engine.start()

    def run_server_proc(self, port, host='0.0.0.0', processes=1, debug=False):
        '''initialise both the api server and input loop'''
        logging.info("load initial peers from SEEDS.txt")
        with open('SEEDS.txt') as h_seeds: #TODO do some verification here.
            peers_urls = set([PROTO + x.strip()+"/" for x in h_seeds.readlines() if not x.startswith('#')])
            for url in peers_urls:
                self.peers[url] = PEER_DICT_NEW
        logging.info("loaded %d peers" % len(self.peers))

        logging.info('Request to run server')
        if self.server_process:
            logging.error('Server already running')
            return None
        self.server_process = Process(target=self.run_server, 
                                    args=[port, host, processes, debug])
        logging.info('Starting web server...')
        self.server_process.start()
        logging.info('Web server started')
        #TODO should have an arg saying whether we're in peer mode or source mode, for now assume source
        self.input_process = Process(target=input_loop_ffmpeg, 
                                    args=[self.slots, self.channels, self.slots._manager])
        logging.info('Starting input loop...')
        self.input_process.start()
        logging.info('Input loop started')
        logging.info('Starting peer discovery thread...')
        pt = threading.Thread(target=self.peer_thread, daemon=True)
        pt.start()
        logging.info('Peer discovery thread started.')
        logging.info('Starting channel discovery thread...')
        ct = threading.Thread(target=self.channel_thread, daemon=True)
        ct.start()
        logging.info('Channel discovery thread started.')        
        logging.info('Init complete!')

    def is_server_running(self):
        if not (bool(self.server_process) | bool(self.input_process)):
            return False
        return self.server_process.is_alive() & self.input_process.is_alive()

    def stop_server_proc(self):
        cherrypy.engine.exit()
        for p in (self.server_process, self.input_process):
            if p.is_alive():
                p.terminate()

#better for processes to be outside object scope?
def input_loop_ffmpeg(slots, channels, manager): 
    '''this really just picks up clips found in the ./channels directory'''
    RE0 = re.compile('OUTPUT(\d+).ts')
    #import pdb; pdb.set_trace()
    count = 0
    while True: #keep scanning for new clips
        scanned = [x for x in os.walk(CHANNELS_DIR)]
        for channel_dir in scanned:
            
            count += 1
            current_segment = 0
            if channel_dir[0] == CHANNELS_DIR:
                continue
            channel = os.path.split(channel_dir[0])[1]
            if not channel in slots.keys():
                slots[channel] = manager.dict()
            if not channel in channels:
                channels.append(channel)
            files = channel_dir[2]
            pt = 0
            while pt < len(files):
                pt+=1
                if (pt - current_segment) < 1:
                    continue
                clip_name = files[current_segment]
                current_segment += 1
                clip_path = os.path.join(CHANNELS_DIR, channel, clip_name)
                stream_num = int(RE0.search(clip_name).groups()[0])
                if stream_num in slots[channel].keys():
                    #print("***ALREADY LOADED")
                    continue
                with open(clip_path, 'rb') as hclip:
                    data = hclip.read()
                if data:
                    logging.info("Loading clip %s/%s" % (channel, clip_name))
                    #print('THREAD: putting clip %s on queue, %d bytes' % (clip_name, len(data)))
                    print('THREAD: putting clip %s on queue, %d bytes' % (clip_path, len(data)))
                    slots[channel][stream_num] = data
            time.sleep(1)
        time.sleep(1)

def input_loop_peers(slots, peers, channel_list, manager):
    clip_counter = 0
    while True:
        time.sleep(1)
        for channel in channel_list:
            #logging.debug("self.slots.keys() = %s" % self.slots.keys())
            #check_kill_flag()
            if slots.get(channel) and clip_counter in slots[channel].keys():
                clip_counter += 1
                logging.info("Already have this clip, sleeping")
                time.sleep(0.5)
                continue
            else:
                if not peers:
                    logging.warning("No peers left!") #TODO this is pretty bad, what do?
                    #time.sleep(4)
                    raise RuntimeException("No more peers!")
                #ask peers if they have this segment
                for peer in random.sample(peers.keys(), len(peers)):
                    if not peers[peer]['registered']:
                        logging.debug("Found peer %s but not registered yet" % peer)
                        continue
                    logging.info("asking peer %s for clip %d" % (peer, clip_counter))
                    clip_url = '%sclip/%s' % (peer, channel)
                    logging.debug("url is %s" % (clip_url))
                    try:
                        resp = requests.get(clip_url, 
                                            params={"key": clip_counter},
                                            timeout=2.0)
                    except ConnectionError:
                        logging.warning("clip - peer %s is down" % peer)
                        continue
                    if resp.status_code == 200:
                        if not channel in slots.keys():
                            slots[channel] = manager.dict()

                        received_file = 'OUTPUT%03d.ts' % clip_counter
                        clip_path = os.path.join(CHANNELS_DIR, channel, received_file)
                        channel_dir = os.path.join(CHANNELS_DIR, channel)
                        if not os.path.exists(channel_dir):
                            os.mkdir(channel_dir)
                        with open(clip_path, 'wb') as hclip:
                            hclip.write(resp.content)
                        #print("*** slots keys are %s" % slots.keys())
                        print("*** channels = %s" % str(list(channel_list)))
                        slots[channel][clip_counter] = resp.content
                        logging.debug("wrote clip %d" % clip_counter)

                    elif resp.status_code == 404: #not found
                        logging.warn("get clip failed with 404, check URL")
                    #once the seed gets a few peers registered it'll issue redirects to them
                    #to prevent getting jammed up with xfers
                    elif resp.status_code == 305: #use proxy
                        logging.info("Seed gave 305 redirect" + str(resp.content))
                        #TODO should try the redirect url now or just throw on pile?
                        url = str(resp.content).lstrip('b').replace("'", "")
                        if not url in peers:
                            #throw on pile
                            peers[url] = PEER_DICT_NEW
        
#DEBUG only
def dbg_print_line_number(frameinfo):
    #HINT call like: dbg_print_line_number(getframeinfo(currentframe()))
    print(frameinfo.filename, frameinfo.lineno)

#must be in global scope to stay alive (?)
manager = Manager()
SLOTS = manager.dict()
PEERS = manager.dict()
CHANNELS = manager.list()
CHANNELS.append("7fd0b650-5185-4d48-9405-e1d16622625e")
STREAM = Stream(SLOTS, PEERS, CHANNELS)


    
if __name__ in ('__main__'):
    #NB these can't be in module scope 
    if __name__ == '__main__':
        try:
            arg_port = int(sys.argv[1])
            mode = sys.argv[2]
        except IndexError:
            print("need a port number and mode")
            sys.exit()
    
    logging.info("load initial peers from SEEDS.txt")
    with open('SEEDS.txt') as h_seeds: #TODO do some verification here.
        peers_urls = set([PROTO + x.strip()+"/" for x in h_seeds.readlines() if not x.startswith('#')])
        for url in peers_urls:
            STREAM.peers[url] = PEER_DICT_NEW
    logging.info("loaded %d peers" % len(STREAM.peers))
    
    if mode == 'source':
        input_process  = Process(target=input_loop_ffmpeg, args=[SLOTS, CHANNELS, SLOTS._manager])
    elif mode == 'seed': #TODO should seed protect address of source peer? Answer: Nah.
        #TODO Q:is it any different to a peer though? How?
        #A: Well, seed would be headless and peer would be GUI and intended for playback.
        #source_url = sys.argv[3] #TODO a headless peer wouldn't know what the source's address is!
        #STREAM.peers.add(source_url)
        #print("INIT: source is %s" % source_url)
        input_process = Process(target=input_loop_peers, args=[SLOTS, PEERS, CHANNELS, SLOTS._manager])
    elif mode == 'peer': #GUI mode mostly
        #seed = sys.argv[3]
        #STREAM.peers.add(seed)
        #print("INIT: seed is %s" % seed)
        #TODO initial seed would come from SEEDS.txt
        input_process = Process(target=input_loop_peers, args=[SLOTS, PEERS, CHANNELS, SLOTS._manager])
    else:
        print("invalid mode, use source | seed | peer")
        sys.exit(1)
    input_process.start()
    STREAM.run_server(arg_port)
    #All modes need peer and channel discovery
    pt = threading.Thread(target=STREAM.peer_thread, daemon=False)
    pt.start()
    ct = threading.Thread(target=STREAM.channel_thread, daemon=False)
    ct.start()
    # all done
    input_process.join()
