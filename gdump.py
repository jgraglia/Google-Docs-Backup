#!/usr/bin/env python
# -*- coding: utf-8 -*-
# https://github.com/jgraglia/Google-Docs-Backup
# Usage : python gdump.py -l xxx@xxxx.com

"""
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

# Google Docs API : 
# http://gdata-python-client.googlecode.com/svn/trunk/pydocs/gdata.docs.data.html#DocsEntry

try:
	import sys
	import argparse
	from types import NoneType
	import getpass
	import os
	import datetime
	import platform
	import shutil
	import signal
	import urllib
	import re
	import time
except:
	print ("failed to find some basic python modules, please validate the environment")
	exit(1)
try:
	import gdata.spreadsheet.service
	import gdata.docs.service
	import gdata.docs.client
except:
	print ("Requires gdata-python-client v2.0+, downloadable from Google at")
	print ("<http://code.google.com/p/gdata-python-client/>")
	exit(1)
try:
        # Add logs functionality
        import logging
        LOG = logging.getLogger("GTRANSFER")
except:
        print "Failed to find logging python modules, please validate the environment"
        exit(1)

# copy from : GDataCopier, http://gdatacopier.googlecode.com/
def signal_handler(signal, frame):
	LOG.debug("\n[Interrupted] Bye Bye!")
	sys.exit(2)


def setup_logger(options):
    msg_format = '%(asctime)s : %(levelname)-8s %(message)s'
    if options.verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    #File
    logging.basicConfig(level=level, format=msg_format, filename="output.log", filemode="w")
    #Console
    console = logging.StreamHandler()
    console.setLevel(level)
    formatter = logging.Formatter('%(asctime)s : %(levelname)-8s %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)
    
    LOG.setLevel(level)
    #LOG.info("test : INFO message")
    #LOG.debug("test : DEBUG message")
    #LOG.warning("test : WARNING message")
    #LOG.error("test : ERROR message")

if __name__ == '__main__':
	signal.signal(signal.SIGINT, signal_handler)
	parser = argparse.ArgumentParser()
	parser.add_argument('-l', '--login', required=True)
	
	args = parser.parse_args()
	args.verbose=False
	setup_logger(args)
	
	oldOwnerPassword = getpass.getpass("Google password  for "+args.login+" : ")
	
	LOG.info ("Connecting with Google account  : "+args.login)
	oldOwner = gdata.docs.client.DocsClient(source="jgraglia-gdump-v1")
	oldOwner.ssl = True 
	oldOwner.http_client.debug = args.verbose
	oldOwner.ClientLogin(args.login, oldOwnerPassword, oldOwner.source);
	LOG.info ("    -> success")

	LOG.info ("Listing all docs of %s"%args.login)
	oldDocsFeed = oldOwner.GetDocList(uri='/feeds/default/private/full/')

	LOG.info ("ACCOUNT DOCUMENT LIST:")
	count=0
	for entry in oldDocsFeed.entry:
		LOG.info ("   - >> "+entry.title.text.encode(sys.getfilesystemencoding()))
		count+=1
	LOG.info(str(count)+" documents found")

