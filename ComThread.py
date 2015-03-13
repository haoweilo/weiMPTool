
import sys,threading,time; 
import serial; 
import binascii,encodings; 
import re; 
import socket; 
import string;
import os;

#### Com Thread Version V1.03

from multiprocessing import Process, Queue;

from ctypes import *;
from struct import *;

def serial_ports():
    """Lists serial ports

    :raises EnvironmentError:
        On unsupported or unknown platforms
    :returns:
        A list of available serial ports
    """
    if sys.platform.startswith('win'):
        ports = ['com' + str(i + 1) for i in range(256)]

    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this is to exclude your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')

    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')

    else:
        raise EnvironmentError('Unsupported platform')

    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result

class ComThread: 
    def __init__(self, Port="com3"): 
        self.l_serial = None; 
        self.alive = False; 
        self.waitEnd = None; 
        self.port = Port;

        self.inter_q = Queue();

        ### for data queue and command queue
        self.dq = None;
        self.cq = None;

    def waiting(self, wait_timeout = 999999): 
        try:
            while not self.waitEnd.isSet():

                self.waitEnd.wait(1);
                if self.inter_q and not self.inter_q.empty():
                    queue_data = self.inter_q.get(True);
                    # to search the keyword when recieve data
                    for keyword in self.listen_keyword:
                            if cmp(keyword, "NONE") != 0 :
                                matcher = re.search(keyword, queue_data);
                                if matcher:
                                    self.waitEnd.set(); 
                                    self.alive = False;
                                    return queue_data;

                if wait_timeout:
                    wait_timeout -= 1;
                else:
                    return None;
                    
            return None

        except KeyboardInterrupt:
            print "stop"
            self.SetStopEvent();
        except Exception, ex: 
            print str(ex);

    def SetStopEvent(self): 
        if not self.waitEnd.isSet(): 
            self.waitEnd.set(); 
        self.alive = False; 
        self.stop();

    def start(self, listen_words="NONE", send_words="NONE"): 
        self.l_serial = serial.Serial(); 
        self.l_serial.port = self.port; 
        self.l_serial.baudrate = 115200; 
        self.l_serial.timeout = 0.2;
        self.l_serial.open();
        if self.l_serial.isOpen():
            self.waitEnd = threading.Event(); 
            self.alive = True; 
            # setup read thread
            self.thread_read = None; 
            # support multi-keywords listen split by "/"
            self.listen_keyword = listen_words.split("/");
            self.thread_read = threading.Thread(target=self.Reader); 
            self.thread_read.setDaemon(1); 
            self.thread_read.start(); 

            # setup write thread
            self.thread_write = None; 

            self.send_keyword = send_words;
            self.thread_write = threading.Thread(target=self.Writer); 
            self.thread_write.setDaemon(1); 
            self.thread_write.start(); 
            return True; 
        else: 
            return False;

    def stop(self): 
        self.alive = False; 
        if self.thread_read.is_alive():
            self.thread_read.join();
        if self.thread_write.is_alive(): 
            self.thread_write.join(); 
        if self.l_serial.isOpen(): 
            self.l_serial.close();

############# Serail Reader and Writer Thread #######################
    def Reader(self): 
        found = 0;
        while self.alive: 

            time.sleep(0.1); 
            try:

                data = ''; 
                n = self.l_serial.inWaiting(); 
                if n : 
                    # Get data from serial interface
                    data = data + self.l_serial.read(n);
                    
                    # to search the keyword when recieve data
                    # data would be expected like "XXXX\nXXXX\nXX"
                    # so it would be splited like "{XXXX, \n , XXX, \n, XX}"
                    for linedata in re.split("(\n)", data):
                        print linedata
                        # update data to the queue
                        # make sure data would a entire line. 
                        if self.dq:
                            self.dq.put(linedata);

                        for words in self.listen_keyword:
                            if cmp(words, "NONE") != 0 :

                                # get rid of the echo command 
                                matcher = re.search("echo \""+words, linedata);
                                if not matcher:

                                    matcher = re.search(words, linedata);
                                    if matcher:
                                        print "Keyword: " + words +" catched";
                                        
                                        if self.inter_q:
                                            self.inter_q.put(words);
                                        else:
                                            ## if no command queue , end the search here.
                                            found = 1;
                                        break;
                        if found:
                            break;

                    #keep the last element which it has no eol symbol (middle of a line) 
                    data = re.split("(\n)", data)[-1];

                    if found:
                        found = 0;
                        break;


            except Exception, ex: 
                print str(ex);


        self.waitEnd.set(); 
        self.alive = False;

    def Writer(self): 
        while self.alive: 

            #time.sleep(0.1); 
            try:
                if cmp(self.send_keyword, "NONE") != 0 :
                    self.l_serial.write(self.send_keyword);

                
            except Exception, ex: 
                print str(ex);
    def ymodem_xmit(self, image_file):
        if sys.platform.startswith('win'):
            # Loading PCOMM DLL for Ymodem xmit
            dll = windll.LoadLibrary("PCOMM.DLL")

            if self.alive == False: 
                # search for com port number....
                port_matcher = re.search(r"\d+$", self.port);
                
                if port_matcher:
                    port_num = port_matcher.group(0);
                else:
                    print "Wrong port Number";
                    return False;
                # start PCOMM DLL API for YMODEM
                dll.sio_open(string.atoi(port_num));
                ### 115200 8N1
                dll.sio_ioctl(string.atoi(port_num), 16, 0x00 | 0x03 | 0x00);

                baudrate = dll.sio_getbaud(string.atoi(port_num));
                print baudrate, image_file

                def cb(xmitlen, buflen, pbuf, flen):
                    print xmitlen, flen,
                    print
                    if flen:
                        ymodem_precent = xmitlen * 100 / flen ;
                        if not ymodem_precent % 7 :
                            if self.dq:
                                self.dq.put("[YMODEM] " + str(ymodem_precent) + "%\n" );
                    return xmitlen

                CALLBACK = WINFUNCTYPE(c_int, c_long, c_int, POINTER(c_char), c_long)
                ccb = CALLBACK(cb)
                dll.sio_FtYmodemTx(string.atoi(port_num), image_file, ccb, 0)
                dll.sio_close(string.atoi(port_num))
                return True;
                # end of PCOMM DLL YMODEM
            else:
                print "Please check the serial port status"
                return False;
        else:
            print "Wrong Platform";
            return False;