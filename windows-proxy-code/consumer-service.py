#   Copyright 2011 Red Hat, Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.


import win32serviceutil
import win32service
import win32event
import win32api
import win32security
import win32con
import win32process
import win32pipe
import win32file
import win32net
import win32netcon
import msvcrt
import os
import threading
import servicemanager
import socket
import platform
from qpid.messaging import *
from qpid.util import URL
import base64
import random
import string

class AppServerSvc (win32serviceutil.ServiceFramework):
    _svc_name_ = "StartConsumer"
    _svc_display_name_ = "Consumer Service"
    _svc_description_ = "Consumer service to process Qpid commands"

    def __init__(self,args):
        win32serviceutil.ServiceFramework.__init__(self,args)
        self.hWaitStop = win32event.CreateEvent(None,0,0,None)
        socket.setdefaulttimeout(60)


    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_,''))

        
        # Create an Administrator account to be impersonated and used for the process
        def create_user():
            params={}
            params['name']= 'RHAdmin'
            digits = "".join( [random.choice(string.digits) for i in range(10)] )
            chars_lower = ''.join( [random.choice(string.ascii_lowercase) for i in range(10)] )
            chars_upper = ''.join( [random.choice(string.ascii_uppercase) for i in range(10)] ) 
            params['password']= digits+chars_lower+chars_upper
            params['password'] = ''.join([str(w) for w in random.sample(params['password'], len(params['password']))])
            params['flags']= win32netcon.UF_NORMAL_ACCOUNT | win32netcon.UF_SCRIPT
            params['priv'] = win32netcon.USER_PRIV_USER

            user = win32net.NetUserAdd(None, 1, params)
            domain = socket.gethostname()
            data = [ {'domainandname' : domain+'\\RHAdmin'} ]
            win32net.NetLocalGroupAddMembers(None, 'Administrators', 3, data)
            return params['password']
        
        try:
            win32net.NetUserDel(None, 'RHAdmin')
            Password = create_user()
        except:
            Password = create_user()
        

        token = win32security.LogonUser('RHAdmin', None, Password, \
        	       win32con.LOGON32_LOGON_INTERACTIVE,
                    win32con.LOGON32_PROVIDER_DEFAULT)
        win32security.ImpersonateLoggedOnUser(token)
        self.main(token)

    def main(self, token):

        connection = Connection('localhost', port=5672)
        connection.open()
        session = connection.session(str(uuid4()))

        receiver = session.receiver('amq.topic')
        local_ip = socket.gethostbyname(socket.gethostname())
        localhost_name = platform.uname()[1]



        def make_inheritable(token):
            """Return a duplicate of handle, which is inheritable"""
            return win32api.DuplicateHandle(win32api.GetCurrentProcess(), token,
                                   win32api.GetCurrentProcess(), 0, 1,
                                   win32con.DUPLICATE_SAME_ACCESS)

        while True:
            message = receiver.fetch()
            session.acknowledge()
            sender = session.sender(message.reply_to)
            command = base64.b64decode(message.content)
            if command.startswith('winrs' or 'winrm') != True or command.find('-r:') == -1 or command.find('localhost') != -1 or command.find(localhost_name) != -1 or command.find(local_ip) != -1:
                sender.send(Message(base64.b64encode('Commands against the proxy are not accepted')))
            else:
                #Start the process:

                # First let's create the communication pipes used by the process
                # we need to have the pipes inherit the rights from token
                stdin_read, stdin_write = win32pipe.CreatePipe(None, 0)
                stdin_read = make_inheritable(stdin_read)

                stdout_read, stdout_write = win32pipe.CreatePipe(None, 0)
                stdout_write = make_inheritable(stdout_write)

                stderr_read, stderr_write = win32pipe.CreatePipe(None, 0)
                stderr_write = make_inheritable(stderr_write)

                # Set start-up parameters the process will use.
                #Here we specify the pipes for input, output and error.
                si = win32process.STARTUPINFO()
                si.dwFlags = win32con.STARTF_USESTDHANDLES
                si.hStdInput = stdin_read
                si.hStdOutput = stdout_write
                si.hStdError = stderr_write


                procArgs = (None,  # appName
                    command,  # commandLine
                    None,  # processAttributes
                    None,  # threadAttributes
                    1,  # bInheritHandles
                    0,  # dwCreationFlags
                    None,  # newEnvironment
                    None,  # currentDirectory
                    si)  # startupinfo

                # CreateProcessAsUser takes the first parameter the token,
                # this way the process will impersonate a user
                try:
                    hProcess, hThread, PId, TId =  win32process.CreateProcessAsUser(token, *procArgs)

                    hThread.Close()

                    if stdin_read is not None:
                        stdin_read.Close()
                    if stdout_write is not None:
                        stdout_write.Close()
                    if stderr_write is not None:
                        stderr_write.Close()

                    stdin_write = msvcrt.open_osfhandle(stdin_write.Detach(), 0)
                    stdout_read = msvcrt.open_osfhandle(stdout_read.Detach(), 0)
                    stderr_read = msvcrt.open_osfhandle(stderr_read.Detach(), 0)


                    stdin_file = os.fdopen(stdin_write, 'wb', 0)
                    stdout_file = os.fdopen(stdout_read, 'rU', 0)
                    stderr_file = os.fdopen(stderr_read, 'rU', 0)

                    def readerthread(fh, buffer):
                        buffer.append(fh.read())

                    def translate_newlines(data):
                        data = data.replace("\r\n", "\n")
                        data = data.replace("\r", "\n")
                        return data

                    def wait():
                        """Wait for child process to terminate.  Returns returncode
                        attribute."""
                        win32event.WaitForSingleObject(hProcess,
                                                        win32event.INFINITE)
                        returncode = win32process.GetExitCodeProcess(hProcess)
                        return returncode


                    def communicate():

                        if stdout_file:
                            stdout = []
                            stdout_thread = threading.Thread(target=readerthread,
                                                             args=(stdout_file, stdout))
                            stdout_thread.setDaemon(True)
                            stdout_thread.start()
                        if stderr_file:
                            stderr = []
                            stderr_thread = threading.Thread(target=readerthread,
                                                             args=(stderr_file, stderr))
                            stderr_thread.setDaemon(True)
                            stderr_thread.start()

                        stdin_file.close()

                        if stdout_file:
                            stdout_thread.join()
                        if stderr_file:
                            stderr_thread.join()

                        if stdout is not None:
                            stdout = stdout[0]
                        if stderr is not None:
                            stderr = stderr[0]

                        if stdout:
                            stdout = translate_newlines(stdout)
                        if stderr:
                            stderr = translate_newlines(stderr)

                        return_code = wait()
                        return (stdout, stderr, return_code)

                    ret_stdout, ret_stderr, retcode =  communicate()


                    result = Message(base64.b64encode(str(ret_stdout)))
                    result.properties["retcode"] = base64.b64encode(str(retcode))
                    if ret_stderr:
                        result.properties["stderr"] = base64.b64encode(str(ret_stderr))
                    else:
                        result.properties["stderr"] = base64.b64encode('')

                    sender.send(result)

                except Exception as exception_message:
                    result = Message(base64.b64encode(''))
                    result.properties["retcode"] = base64.b64encode(str(exception_message[0]))
                    result.properties["stderr"] = base64.b64encode(str(exception_message[2]))

                    sender.send(result)

