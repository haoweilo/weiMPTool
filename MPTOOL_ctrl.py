#  bootstrap.py

import sys,threading,time; 
import serial; 
import binascii,encodings; 
import re; 
import socket; 
import string;
import Tkinter;
import tkFileDialog;
import glob;
import tkMessageBox;

import vlc

from multiprocessing import Process, Queue;
import os;

from Tkinter import *;
from ctypes import *;
from struct import *;

# using DOM XML parser
from xml.dom.minidom import parse
import xml.dom.minidom

from ComThread import *;

####### Version #################
VERSION = "V1.03.1";
# v.1.0.3 improve text refresher
# v.1.0.3.1 add SonixIPCamVerifier keyword support

player = vlc.MediaPlayer();

########## Start ###################################
def do_cmd(exefile="c:\\sonix\\SonixIPCamVerifier\\IPCamVerifier.exe"):

    if os.path.isfile(os.path.abspath(exefile)) and os.access(os.path.abspath(exefile), os.F_OK):

            os.startfile(os.path.abspath(exefile));
    else:
        print '%s does not exist' %(exefile)
        warning("warning", exefile+"does not exist");

def param_check(port, script_file = None):

    global port_num;

    # search for com port number....
    port_matcher = re.search(r"\d+$", port);
    
    if port_matcher:
        port_num = port_matcher.group(0);
    else:
        print "wrong port number"
        warning("warning", "wrong port number");
        return False

    if not script_file is None:
        if not os.path.isfile(script_file):
            print "wrong file";
            warning("warning", "wrong file: "+ script_file);
            return False

    return True;


def start_to_execute(port, script_file, data_queue):

    wait_timeout = 40;
    ret = param_check(port, script_file);
    if not ret:
        return ret

    ################ start ##################
    rt = ComThread();

    # assign port to rt
    rt.port = port;

    rt.dq = data_queue;

    try: 
        data_queue.put("[Start to Execute]\n");
        data_queue.put("*LABEL_RESET\n");

        ########### start to execute ##############
        if rt.start("PASS/FAIL/ASK_RESULT", "NONE"):

            print "[Test Item] issues test commands"
            data_queue.put("[Test Item] issues test commands\n");

            # run the scripts
            f=open(os.path.abspath(script_file), 'r');

            for line in f.readlines():

                # the keyword no need to be issued
                if re.search("#PAUSE#", line):
                    #print "#PAUSE# tag received";
                    warning("Pause", line);
                    continue;
                elif re.search("#TIMEOUT#", line):
                    #print "#TIMEOUT# tag received";
                    matcher = re.search(r"\d+$", line);
                    if matcher:
                        wait_timeout = int(matcher.group(0).strip());
                    continue;
                elif re.search("#SLEEP#", line):
                    #print "#SLEEP# tag received";
                    time.sleep(1); 
                    continue;
                elif re.search("#YESNO#", line):
                    #print "#YESNO# tag received";
                    temp_frame = Tkinter.Tk() 
                    temp_frame.withdraw() 
                    if tkMessageBox.askyesno("Please check", line, master=temp_frame):
                        # if the check is PASS
                        continue;
                    else:
                        data_queue.put("*FAIL " + script_file +"\n");
                        rt.SetStopEvent();
                        break;
                    temp_frame.deiconify() 
                    temp_frame.destroy();
                
                elif re.search(r"^#", line) or not cmp(line, "\n"):
                    #print "commment tag received";
                    continue;

                rt.l_serial.write(line.strip("\t"));
                
                # the keyword should be wait.
                if re.search(r"^sleep", line):
                    print "sleep tag received";
                    time.sleep(int(re.search(r"\d+$", line).group(0))); 

                time.sleep(0.5); 
            # close the file
            f.close();

            ret = rt.waiting(wait_timeout);
                
            rt.SetStopEvent();
            if ret is None:
                data_queue.put("*FAIL Timeout\n");
            else:
                print ret;
                if re.search("ASK_RESULT", ret):
                    print "ASK_RESULT tag received"
                    temp_frame = Tkinter.Tk() 
                    temp_frame.withdraw() 
                    if tkMessageBox.askyesno("check", u"Work Properly?", master=temp_frame):

                        data_queue.put("*PASS " + script_file +"\n");
                    else:
                        data_queue.put("*FAIL " + script_file +"\n");
                    temp_frame.deiconify() 
                    temp_frame.destroy();
                else:
                    data_queue.put("*"+ret+" " + script_file +"\n");

        else:
            pass;

    except KeyboardInterrupt:
        print "stop"
        rt.SetStopEvent();
    except Exception,se: 
        print str(se);


def start_to_checkstatus(port, data_queue):

    ret = param_check(port);
    if not ret:
        return ret

    ################ start ##################
    rt = ComThread();

    # assign port to rt
    rt.port = port;

    rt.dq = data_queue;

    try: 
        data_queue.put("[Start to Check]\n");
        data_queue.put("*LABEL_RESET\n");
        ###########  Stage 1 Stop it in bootstrap ##############
        # Wait for Linux bootup
        if rt.start(listen_words="login/~ #"): 
            rt.l_serial.write("\n");

            ## wait for 30 timeout
            ret = rt.waiting(30);

            rt.SetStopEvent();
            if ret is None:
                data_queue.put("*FAIL Timeout\n");
                return False;
            else:
                matcher = re.search("~ #", ret);
                if matcher:
                    data_queue.put("*PASS Ready to Test\n");
                    return True;
        else: 
            pass;

        # Wait for Linux login 
        if rt.start(listen_words= "~ #"): 
            rt.l_serial.write("\n");
            time.sleep(1); 
            rt.l_serial.write("root\n");
            time.sleep(0.3); 
            rt.l_serial.write("1234\n");

            ## wait for 30 timeout
            ret = rt.waiting(30);
            rt.SetStopEvent();
            if not ret is None:
                data_queue.put("*PASS Ready to Test\n");
                return True;
            else:
                data_queue.put("*FAIL Timeout\n");
                return False;
        else: 
            pass;

        
    except KeyboardInterrupt:
        print "stop"
        rt.SetStopEvent();
    except Exception,se: 
        print str(se);

### Fake burn process for testing #####

#def fake_burn(port, script_file, data_queue):
#    # run hw setting scripts
#    f=open(script_file, 'r');
#    for line in f.readlines():
#        data_queue.put(line);
#        time.sleep(0.3); 
#    f.close();

### button click handler ####
def click_check_status_button():
    
    global status_process;
    global text_queue;

    if not port_listbox.curselection():
        print "NO port selected";
        warning("warning", "NO port selected ");
        return False;

    port = port_listbox.get(port_listbox.curselection());


    if not status_process.is_alive():

        status_process = Process(target=start_to_checkstatus, name='status_process', args=(port,text_queue, ));
        status_process.start();
        check_status_button.config(text = "Checking...", state=DISABLED);
        print 'process %s starts to run...' % status_process.name;


### button click handler ####
def click_start_button():
    
    global burn_process;
    global text_queue;
    global configs_list;
    global player;

    if not port_listbox.curselection():
        print "NO port selected";
        warning("warning", "NO port selected ");
        return False;

    port = port_listbox.get(port_listbox.curselection());

    ## Get the selected test item
    if not item_listbox.curselection():
        print "NO test item selected";
        warning("warning", "NO test item selected ");
        return False;

    test_item = item_listbox.get(item_listbox.curselection());
    print test_item + " is selected" + str(item_listbox.curselection());
    script_file = str(configs_list[item_listbox.curselection()[0]]["ScriptPath"]);



    if not burn_process.is_alive():

        burn_process = Process(target=start_to_execute, name='burn_process', args=(port,script_file,text_queue, ));
        #burn_process = Process(target=fake_burn, name='burn_process', args=(port,script_file,text_queue,));
        burn_process.start();
        time.sleep(0.3);
        start_button.config(text = "STOP");
        print 'process %s starts to run...' % burn_process.name;

    else:
        burn_process.terminate();
        # Stop Player 
        if player:
            player.stop();
        time.sleep(0.3);
        start_button.config(text = "START");
        print 'process %s is stopping...' % burn_process.name;

### file selector
def HW_Setting_FileSelector():
   filename = tkFileDialog.askopenfilename(parent=main_frame,title='Choose HW setting file')
   scripts_path.set(filename);

   text.config(state=NORMAL);
   text.insert(END, scripts_path_entry.get() + "\n");

   #handle port selection
   text.insert(END, port_listbox.get(port_listbox.curselection()) + "\n");
   text.config(state=DISABLED);
   print scripts_path_entry.get()

def Image_FileSelector():
   filename = tkFileDialog.askopenfilename(parent=main_frame,title='Choose Image File')
   image_path.set(filename);
   text.config(state=NORMAL);
   text.insert(END, image_path_entry.get() + "\n");
   text.config(state=DISABLED);

   print image_path_entry.get()

### text refresher ###
def Text_Refresher(data_queue, text_widget):
    global text_refresher_thread_flag;
    global player;

    while text_refresher_thread_flag:

        queue_data = data_queue.get(True);

        if not re.search(r"^\*", queue_data) is None:

        
            if not re.search("\*PASS", queue_data) is None:

                result_label_str.set("Result:\n" + queue_data);
                result_label.config(bg="green")
                start_button.config(state=NORMAL);

            elif not re.search("\*FAIL", queue_data) is None:

                result_label_str.set("Result:\n" + queue_data);
                result_label.config(bg="red")
                start_button.config(state=DISABLED);

            elif not re.search("\*LABEL_RESET", queue_data) is None:
                result_label_str.set("\n");
                result_label.config(bg="yellow")

            elif not re.search("\*VLC", queue_data) is None:
                #avoid take the echo command #
                matcher = re.search("echo \"\*VLC", queue_data);
                if not matcher:
                    #print "#VLC# tag received";
                    MRL = re.split("\*VLC[ \t]+",queue_data);
                    print "VLC Player start to play " + MRL[-1];
                    vlc_version_str = vlc.libvlc_get_version();
                    print "VLC Version "+ vlc_version_str;
                    v1,v2,v3 = re.search(r"^[0-9.]+",vlc_version_str).group(0).split(".");
                    if int(v1) != 2 or int(v2) != 1:
                        warning("FAIL", "Please 2.1.X version VLC");
                    else :
                        player.set_mrl(MRL[-1].strip(), ":network-caching=400");
                        player.play();

            elif not re.search("\*SonixIPCamVerifier", queue_data) is None:
                #avoid take the echo command #
                matcher = re.search("echo \"\*SonixIPCamVerifier", queue_data);
                if not matcher:
                    #print "SonixIPCamVerifier tag received";
                    SNX_IPCVERIFY = re.split("\*SonixIPCamVerifier[ \t]+",queue_data);
                    print "IPCamVerifier : " + SNX_IPCVERIFY[-1];
                    do_cmd();
        else:
            text_widget.insert(END, queue_data);
            text_widget.see(END);

        time.sleep(0.02);

### Task_monitor ###
def Task_monitor():
    global run_flag;
    global burn_process;
    while run_flag:
        if not burn_process.is_alive():
            start_button.config(text = "START");
        else:
            start_button.config(text = "STOP");

        if not status_process.is_alive():
            check_status_button.config(text = "Check Status", state=NORMAL);

        time.sleep(1);

### message box ####
def warning(w_title, w_message):
    temp_frame = Tkinter.Tk() 
    temp_frame.withdraw() 
    tkMessageBox.showinfo(w_title, w_message, master = temp_frame);
    temp_frame.deiconify() 
    temp_frame.destroy();

### The Task handler when the main window is exiting
def main_frame_leaving():
    global text_refresher_thread_flag;
    print "Exit main_frame";
    while burn_process.is_alive():
        burn_process.terminate();
    while status_process.is_alive():
        status_process.terminate();

    if player:
    	player.stop();
        player.release();

    text_refresher_thread_flag = False;
    run_flag = False;
    main_frame.destroy();

### XML parsing function ####
def get_attrvalue(node, attrname):
     return node.getAttribute(attrname) if node else ''

def get_nodevalue(node, index = 0):
    return node.childNodes[index].nodeValue if node else ''

def get_xmlnode(node,name):
    return node.getElementsByTagName(name) if node else []

def find_config_id(configs,id):
    # Print detail of each configs.
    id = [];
    for i in configs:
       print "***** MPTOOL Configs*****"

       id = get_attrvalue(i,"id");
       TitleName  = get_nodevalue(Title_node[0]);
       print "TitleName: %s" % TitleName;

    return node.getElementsByTagName(name) if node else []
 
########## Main ####################################
if __name__ == '__main__': 

    # Open XML document using minidom parser
    DOMTree = xml.dom.minidom.parse("config.xml");
    collection = DOMTree.documentElement;


    # Get all the movies in the collection
    mptool_configs = get_xmlnode(collection,"config");

    configs_list = [];
    config_id = 0;
    # Print detail of each configs.
    for configs in mptool_configs:
        print "***** MPTOOL Configs*****"

        #config_id = get_attrvalue(configs,"id");
        #if configs.hasAttribute("id"):
        #    print "Root element : %s" % configs.getAttribute("id");
        config_id += 1;

        ### fetch all tags data to construct a dict list
        Title_node = get_xmlnode(configs,"Title");
        config_title  = get_nodevalue(Title_node[0]);

        scriptpath_node = get_xmlnode(configs,"ScriptPath");
        config_script  = get_nodevalue(scriptpath_node[0]);

        configs_item = {};
        configs_item['id'] , configs_item['Title'] , configs_item['ScriptPath']  = (
            int(config_id), config_title , config_script
        )
        configs_list.append(configs_item);
        print configs_item;


    ##### GUI construction ##########################

    main_frame = Tkinter.Tk()

    main_frame.title("MPTOOL " + VERSION);

    ### main label
    label1 = StringVar()

    label1.set("MPTOOL ")

    title_label = Label(main_frame, fg = "red", textvariable=label1, padx=20, pady=20)

    ### ListBox for port selection ####
    label4 = StringVar();
    label4.set("select a valid port");
    port_list_label = Label(main_frame, textvariable=label4);

    port_list = serial_ports();
    port_listbox = Listbox(main_frame, selectmode = SINGLE, bd = 2,fg = "yellow", selectbackground = "black", width=25, height=6, exportselection = 0);
    if port_list:
        for i in port_list:
            port_listbox.insert(END, i);
        port_listbox.selection_set(END);
    else:
        print "No Valid port";
        warning("warning", "No Valid port");

    ### ListBox for Test items ####
    label5 = StringVar();
    label5.set("select a Test item");
    item_list_label = Label(main_frame, textvariable=label5);

    item_listbox = Listbox(main_frame, selectmode = SINGLE, bd = 2,fg = "blue", selectbackground = "black",width=34, height=6, exportselection = 0);
    if configs_list:
        for configs in configs_list:
            item_listbox.insert(END, str(configs["id"])+ "_" + configs["Title"]);
        item_listbox.selection_set(0);
    else:
        print "No Valid Test items";
        warning("warning", "No Valid Test Items");

    item_scrollbar = Scrollbar(main_frame,command = item_listbox.yview);
    item_listbox["yscrollcommand"] = item_scrollbar.set;

    #### Result Label
    result_label_str = StringVar();
    result_label_str.set("Result:");
    result_label = Label(main_frame, textvariable=result_label_str, width= 34, height= 3, bg = "gray");

    """### hw_setting selector ####
    label2 = StringVar();
    label2.set("hw setting path");
    hw_setting_label = Label(main_frame, textvariable=label2);

    scripts_path = StringVar();
    hw_setting_file_buton = Tkinter.Button(main_frame, text ="Script Path", command = HW_Setting_FileSelector);
    scripts_path_entry = Entry(main_frame, bd =2, textvariable = scripts_path);
    scripts_path.set("st58600e2_burn_UBOOT_from_uart.d");

    ### image selector
    label3 = StringVar();
    label3.set("UBOOT path");
    image_path_label = Label(main_frame, textvariable=label3);

    image_path = StringVar();
    image_file_buton = Tkinter.Button(main_frame, text ="Image File", command = Image_FileSelector);
    image_path_entry = Entry(main_frame, bd =2, textvariable = image_path);
    image_path.set("UBOOT.bin");
    """

    ### text with scrollbar #####
    
    text = Text(main_frame,bg = "gray", height=10, width=50);
    
    text_scrollbar = Scrollbar(main_frame,command = text.yview);
    text["yscrollcommand"] = text_scrollbar.set;
    # set text as readonly

    ### text refresher threading start
    text_refresher_thread_flag = True;
    text_queue = Queue();
    thread_text_refresher = threading.Thread(target=Text_Refresher, args=(text_queue,text,)); 
    thread_text_refresher.setDaemon(1); 
    thread_text_refresher.start();

    ###### Check Status Button 
    status_process = Process();
    check_status_button = Tkinter.Button(main_frame, text ="Check Status", command = click_check_status_button);
    check_status_button.config(bd = 4, fg = "red");

    ### start button
    ###### burn multiprocess delaration
    burn_process = Process();
    start_button = Tkinter.Button(main_frame, text ="START", command = click_start_button);
    start_button.config(bd = 4, fg = "red");
    # Disable first, wait for the status check
    start_button.config(state=DISABLED);

    run_flag = True;
    thread_task_monitor = threading.Thread(target=Task_monitor); 
    thread_task_monitor.setDaemon(1); 
    thread_task_monitor.start(); 

    # Code to add widgets will go here...
    row_index = 0;
    title_label.grid(row = row_index, columnspan=3 );

    """row_index += 1;
    hw_setting_label.grid(row = row_index, column=0, sticky = E);
    scripts_path_entry.grid(row = row_index, column = 1);
    hw_setting_file_buton.grid(row = row_index, column = 2, sticky = W);

    row_index += 1;
    image_path_label.grid(row = row_index, column=0, sticky = E);
    image_path_entry.grid(row = row_index, column = 1);
    image_file_buton.grid(row = row_index, column = 2, sticky = W);
    """

    ### Check Boot Status Button
    row_index += 1;
    check_status_button.grid(row = row_index, column=0);    

    result_label.grid(row = row_index, column=1, columnspan=2);

    ### Test items List Box
    row_index += 1;
    item_list_label.grid(row = row_index, column=0, sticky = E);
    item_listbox.grid(row = row_index, columnspan=2, column = 1);
    item_scrollbar.grid( row = row_index,columnspan=2, column=3, sticky = NS)

    ### Port List Box
    row_index += 1;
    port_list_label.grid(row = row_index, column=0, sticky = E);
    port_listbox.grid(row = row_index, column = 1);

    ### Start Test Button
    start_button.grid(row = row_index, column=2);

    
    row_index += 1;
    text.grid(row = row_index, columnspan=3);
    text_scrollbar.grid( row = row_index, columnspan=3,column=3, sticky = NS)

    main_frame.protocol("WM_DELETE_WINDOW", main_frame_leaving);
    main_frame.mainloop();
