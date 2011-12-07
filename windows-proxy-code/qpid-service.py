#!/usr/bin/env python
# encoding: utf-8

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
import servicemanager
import socket
import platform
from subprocess import Popen, STDOUT, PIPE


class AppServerSvc (win32serviceutil.ServiceFramework):
    _svc_name_ = "StartQpid"
    _svc_display_name_ = "Qpid broker service"
    _svc_description_ = "Qpid windows "

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
        self.main()

    def main(self):
        proc = Popen('\"c:\\Program Files (x86)\\Apache\\qpidc-0.10\\bin\\qpidd.exe"', shell=True)
        proc.wait()
                

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(AppServerSvc)







