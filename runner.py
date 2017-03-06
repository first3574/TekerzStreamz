import win32gui
import subprocess
import time
import pickle
import paramiko

from threading import Thread

ssh_vision = paramiko.SSHClient()
ssh_vision.set_missing_host_key_policy(paramiko.AutoAddPolicy())

ssh_stream = paramiko.SSHClient()
ssh_stream.set_missing_host_key_policy(paramiko.AutoAddPolicy())

VISION_ADDRESS = '10.35.74.201'
STREAM_ADDRESS = '10.35.74.202'

class Configurator:
    __window_handles = set()
    __db_file = "streamconf.pkl"
 
    __db = {}
 
    try:
        __db = pickle.load(open(__db_file, "rb"))
    except IOError:
        pass
 
    @staticmethod
    def seen_windows():
        return Configurator.__window_handles
 
    @staticmethod
    def register_window(hwnd):
        Configurator.__window_handles.add(hwnd)
 
    @staticmethod
    def get_stream_layout(name):
        if name in Configurator.__db:
            return Configurator.__db[name]
        return None
 
    @staticmethod
    def update_stream_layout(name, rect):
        Configurator.__db[name] = rect
        pickle.dump(Configurator.__db, open(Configurator.__db_file, "wb"))
 
 
class VideoStream(Thread):
    def __init__(self, port, name):
        Thread.__init__(self)
        self.port = port
        self.name = name
        self.hwnd = 0
        self.running = False
        self.died = False
        self.proc = 0
        self.winrect = None
 
    def run(self):
        while True:
            time.sleep(1.0)
            newrect = win32gui.GetWindowRect(self.hwnd)
 
            if not (self.winrect and
                    newrect[0] == self.winrect[0] and
                    newrect[1] == self.winrect[1] and
                    newrect[2] == self.winrect[2] and
                    newrect[3] == self.winrect[3]):
 
                self.winrect = newrect
 
                Configurator.update_stream_layout(self.name, {'x': self.winrect[0],
                                                              'y': self.winrect[1],
                                                              'w': self.winrect[2] - self.winrect[0],
                                                              'h': self.winrect[3] - self.winrect[1]})
 
 
    def go(self):
        self.proc = subprocess.Popen(r'c:\gstreamer\1.0\x86_64\bin\gst-launch-1.0 udpsrc port={} caps="application/x-rtp" ! rtph264depay ! avdec_h264 ! autovideosink sync=false'.format(self.port), shell=True, stderr=subprocess.STDOUT)
        self.running = True
 
        seen = Configurator.seen_windows()
 
        while self.hwnd == 0 and self.hwnd not in seen:
            time.sleep(0.5)
            self.hwnd = win32gui.FindWindow(None, 'GStreamer D3D video sink (internal window)')
            time.sleep(0.01)
 
        Configurator.register_window(self.hwnd)
 
        l = Configurator.get_stream_layout(self.name)
 
        if l:
            win32gui.MoveWindow(self.hwnd, l['x'], l['y'], l['w'], l['h'], True)
 
        win32gui.SetWindowText(self.hwnd, self.name)
 
        self.start()
 
REMOTE_STREAM_COMMAND = 'sleep 1 && gst-launch-1.0 v4l2src device=/dev/video{} ! "video/x-raw,width=640,height=480,framerate=30/1" ! x264enc speed-preset=1 tune=zerolatency bitrate=1024 ! rtph264pay ! udpsink host={} port={} &'

if __name__ == "__main__":
    ssh_stream.connect(STREAM_ADDRESS, username='odroid', password='odroid', port=5800)
    ssh_vision.connect(VISION_ADDRESS, username='odroid', password='odroid', port=5800)
    ssh_stream.exec_command("killall gst-launch-1.0")
    ssh_stream.exec_command("killall run_vision.sh")
    stdin, stdout, stderr = ssh_stream.exec_command('env | grep SSH_CONNECTION')
    connection_info = stdout.readlines()[0].partition("=")[2]
    our_ip = connection_info.partition(" ")[0]
    print(our_ip)

    ssh_vision.exec_command("export DRIVERSTATION_IP={}".format(our_ip))
    ssh_stream.exec_command(REMOTE_STREAM_COMMAND.format('0', our_ip, '5805'))
    vs1 = VideoStream(5805, "Camera 1")
    vs1.go()

    ssh_vision.exec_command("DRIVERSTATION_IP={} ./run_vision.sh &".format(our_ip))
    vs2 = VideoStream(5800, "Vision 1")
    vs2.go()
    #vs3 = VideoStream(5802, "Camera 3")
    #vs3.go()
    #vs4 = VideoStream(5803, "Camera 4")
    #vs4.go()

    #vs1.proc.wait()
