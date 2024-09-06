
def input_loop_copier(SLOTS): 
    RE0 = re.compile('OUTPUT(\d+).ts')

    pt = 1
    while True:
        check_kill_flag()
        try:
            NOTIFY.pop()
            print "THREAD NOTIFIED!"
        except IndexError:
            print "THREAD WAITING!"
            time.sleep(0.5)
            continue
        files = glob.glob("OUTPUT*.ts")
        files.sort(key = lambda x: ''.join([c for c in x if c in string.digits]).zfill(4))
        if pt > len(files):
            time.sleep(0.5)
            continue
        clip = files[pt-1]
        pt+=1
        with open(clip, 'rb') as hclip:
            data = hclip.read()
        if data:
            #print 'THREAD: putting clip %s on queue' % clip
            stream_num = int(RE0.search(clip).groups()[0]) + 1
            SLOTS[stream_num] = data
            #os.unlink(clip)
            #print "THREAD: SLOTS size is %s" % len(SLOTS)
            #print "THREAD: SLOTS.keys() = %s" % sorted(SLOTS.keys())
        time.sleep(2)

#not sure if this needed, can you kill by process id
def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    logging.info("**shutting down werkzeug server with PID %d" % os.getpid())
    func()

def check_kill_flag():
    if os.path.exists('../kill'):
         shutdown_url = "http://0.0.0.0:%s/shutdown" % arg_port
         logging.info("caught kill flag, sending shutdown to %s" % shutdown_url)
         requests.get(shutdown_url)
         logging.info("Exiting PID %d" % os.getpid())
         sys.exit(0)


def copy_thread():
    i = 0
    os.chdir("FF_segs")
    files = glob.glob("OUTPUT*.ts")
    files.sort(key = lambda x: ''.join([c for c in x if c in string.digits]).zfill(4))
    qf = deque(files)
    while qf:
        orig = qf.popleft()
        filename = os.path.split(orig)[1]
        media_info = MediaInfo.parse(orig)
        duration = [t['duration'] for t in media_info.to_data()['tracks'] 
                     if t['track_type'] =='Video'][0] / 1000.0
        try:
            shutil.copy(orig, '..')
            os.rename(filename, filename)
            #os.rename(filename, filename + ".READY")
            NOTIFY.append(True)
            if len(NOTIFY)>1:
                raise RuntimeError
        except OSError:
            print "THREAD2: oops!"
        print "THREAD2 copied %s" % orig
        print "THREAD2 sleeping %f" % duration
        #print "THREAD2! %f" % time.time()
        time.sleep(duration)

def playlist_fake(request):
    pl = \
'''#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:14
#EXT-X-MEDIA-SEQUENCE:0
#EXTINF:10.000000,
stream0.ts
#EXTINF:10.000000,
stream1.ts
#EXTINF:10.000000,
stream2.ts
#EXTINF:13.200000,
stream3.ts
#EXTINF:11.040000,
stream4.ts
#EXTINF:10.000000,
stream5.ts
#EXTINF:6.640000,
stream6.ts
#EXT-X-ENDLIST
'''
    return pl


