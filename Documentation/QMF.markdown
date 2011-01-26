Title: Image Factory QMF API
Format: complete
Author: Steve Loranz
Date: January 26, 2011
Revision: 1.0
Keywords: aeolus,image_factory,cloud,qmf,qmf2,api

**Introduction**
----------------
Running imagefactory.py without any options will start a QMF agent that tries to connect to a QPID broker on localhost by default.  Image Factory can connect to a qpidd you specify using the '--url URL' option.

Once the agent has opened a session with the broker, QMF consoles can send messages to the agent start image builds, get status on builds, etc.

**Image Factory Agent**
-----------------------
