#!/usr/bin/env python
# -*- coding: utf-8 -*-
# https://github.com/jgraglia/Google-Docs-Backup
# Usage : python gtransfer.py -l xxx@xxxx.com -o yyy@yyyyy.com

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

__update_url="https://github.com/jgraglia/Google-Docs-Backup/raw/master/gtransfer.py"
__version=0.2
	
# copy from : GDataCopier, http://gdatacopier.googlecode.com/
# windows problem :  "|*><?
__bad_chars__ = ['\\', '/', '&', ':', '|', '*', '>', '<', '?', '"']

# Strips characters that are not acceptable as file names
# copy from : GDataCopier, http://gdatacopier.googlecode.com/
def sanatize_filename(origFileName):
	try :
		filename = origFileName.decode(sys.getfilesystemencoding())
	except UnicodeEncodeError:
		try:
			filename = origFileName.decode('UTF-8')
		except UnicodeEncodeError:
			filename= origFileName
	for bad_char in __bad_chars__:
		filename = filename.replace(bad_char, '')
		
	filename = filename.lstrip().rstrip()
	return filename.encode(sys.getfilesystemencoding())

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

#not all doc type are support for Copy. see Google API
def canTransferOwnership(entry):
	if entry.GetDocumentType()== "document" :
		return True
	elif entry.GetDocumentType() == "presentation":
		return True
	elif entry.GetDocumentType() == "spreadsheet":
		return True
	elif entry.GetDocumentType() == "drawing":
		return True
	else :
		return False

def computeFileNameFor(entry, ext):
	return sanatize_filename(entry.title.text)+ext

def computeFileForEntry(client, stdToken, spreadsheetToken, storeFolder, entry, filenameToCreate, storeFlat, ignoreDualCollections):
	if storeFlat == True:
		return computeFlatFileForEntry(storeFolder, entry, filenameToCreate)
	else:
		return computeArborescentFileForEntry(client, stdToken, spreadsheetToken, storeFolder, ignoreDualCollections, entry, filenameToCreate)

def computeFlatFileForEntry(storeFolder, entry, filenameToCreate):
	return os.path.join(os.path.abspath(storeFolder), filenameToCreate)

def computeArborescentFileForEntry(client, stdToken, spreadsheetToken, storeFolder, ignoreDualCollections, entry, filenameToCreate):
	firstFolder=getFirstCollectionFolderFor(client, stdToken, spreadsheetToken, storeFolder, entry,ignoreDualCollections)
	if firstFolder==None:
		return os.path.join(os.path.abspath(storeFolder), filenameToCreate)
	else:				
		colFolder = os.path.join(os.path.abspath(storeFolder), firstFolder.title)
		forceFolder(colFolder)
		return os.path.join(os.path.abspath(colFolder), filenameToCreate)

def isOwnerOfFolder(folderAsLink, login, stdToken, spreadsheetToken):
	folderId = folderAsLink.href.split('/')[-1]
	if args.verbose:
		LOG.debug ("Trying to access to folder '"+folderAsLink.title+"' ("+folderId+") as user :  "+login)
	try:
		client.auth_token = stdToken
		folderAsGData = client.GetDoc(folderId)
		aclFeed = client.GetAclPermissions(folderAsGData.resource_id.text)
		for acl in aclFeed.entry:
			if args.verbose:
				print (acl.scope.value+' ('+acl.scope.type+') is '+acl.role.value+' of '+folderAsGData.title.text)
			if acl.role.value == "owner" and acl.scope.value== login:
				return True
		return False
	except gdata.client.Unauthorized  as error:
		LOG.error ("No access to folder "+folderAsLink.title.text.encode(sys.getfilesystemencoding())+" : it seems that "+login+" is  not the owner of that folder")
		LOG.error ("Error: {0}".format(error))
		return False	

def logAndProposeAbort(error):
	LOG.error("Error "+str(error));
	LOG.error ("Error: {0}".format(error))
	proposeAbort()

def proposeAbort():
	if sys.version_info >= (3, 0):
		input("You can abort now (CTRL+C), or press ENTER when the error is resolved")
	else:
		raw_input("You can abort now(CTRL+C), or press ENTER when the error is resolved")

def pressAKeyToContinue():
	if sys.version_info >= (3, 0):
		input("Enter to continue...")
	else:
		raw_input("Enter to continue...")

def isWriter(client, entry, login):
	aclFeed = client.GetAclPermissions(entry.resource_id.text)
	for acl in aclFeed.entry:
		if acl.role.value == "writer" and acl.scope.value== login:
			return True
	return False

def addWriterShareIfNotAlready(client, entry, login):
	if isWriter(client, entry, login):
		LOG.info ("   - No need to add WRITER share to "+login+" on "+entry.title.text.encode(sys.getfilesystemencoding())+" : already Writer")
	else:
		LOG.info ("   - Adding WRITER share to "+login+" on "+entry.title.text.encode(sys.getfilesystemencoding()))
		if not args.dryRun:
			newScope = gdata.acl.data.AclScope(value=login, type='user')
			newRole = gdata.acl.data.AclRole(value="writer")
			newAcl_entry = gdata.docs.data.Acl(scope=newScope, role=newRole)
			try :
				uri = entry.GetAclLink().href+"?send-notification-emails=true"
				created_acl_entry = client.Post(newAcl_entry, uri)
				stats['addwriter']+=1
			except gdata.client.RequestError as error :
				LOG.error("Current ACL for entry")
				aclFeed = client.GetAclPermissions(entry.resource_id.text)
				for acl in aclFeed.entry:
					LOG.error("        acl : "+str(acl.scope.value)+' ('+str(acl.scope.type)+') is '+str(acl.role.value)+' of '+entry.title.text.encode(sys.getfilesystemencoding()))
				logAndProposeAbort(error)
		else:
				stats['addwriter']+=1

def removeAllRightsExceptMine(client, entry, targetLogin):
	LOG.info ("   - Removing ALL rights of "+targetLogin+" on "+entry.title.text.encode(sys.getfilesystemencoding()))
	aclFeed = client.GetAclPermissions(entry.resource_id.text)
	for acl in aclFeed.entry:
		if not acl.scope.value==targetLogin:
			LOG.info("        removing acl : "+str(acl.scope.value)+' ('+str(acl.scope.type)+') is '+str(acl.role.value)+' of '+entry.title.text.encode(sys.getfilesystemencoding()))
			if not args.dryRun:
				try:
					client.Delete(acl, force=True)
					stats['removeAllRightsExceptMine']+=1
				except gdata.client.RequestError as error :
					logAndProposeAbort(error)
			else:
				stats['removeAllRightsExceptMine']+=1

def removeAllRightsIfNotOwned(client, entry, targetLogin):
	if not isOwner(client, entry, targetLogin):
		LOG.info ("   - Removing ALL rights of "+targetLogin+" on "+entry.title.text.encode(sys.getfilesystemencoding()))
		aclFeed = client.GetAclPermissions(entry.resource_id.text)
		for acl in aclFeed.entry:
			if acl.scope.value == targetLogin:
				LOG.info("        removing acl : "+str(acl.scope.value)+' ('+str(acl.scope.type)+') is '+str(acl.role.value)+' of '+entry.title.text.encode(sys.getfilesystemencoding()))
				if not args.dryRun:
					try:
						client.Delete(acl, force=True)
						stats['removeoldownerright']+=1
					except gdata.client.RequestError as error :
						logAndProposeAbort(error)
				else:
					stats['removeoldownerright']+=1
		return True
	else:
		LOG.debug("   - Keeping safe owner doc of "+targetLogin+" : "+entry.title.text.encode(sys.getfilesystemencoding()))
		return False

def isOwner(client, entry, targetLogin):
	aclFeed = client.GetAclPermissions(entry.resource_id.text)
	for acl in aclFeed.entry:
		if acl.role.value == "owner" and acl.scope.value== targetLogin:
			return True
	return False

def makeCopy(client, entry, oldLogin, newLogin):
	if canTransferOwnership(entry):
		LOG.info("Copying : "+str(entry.title.text.encode(sys.getfilesystemencoding())))
		if not args.dryRun:
			try:
				duplicated_entry = client.Copy(entry, entry.title.text.encode(sys.getfilesystemencoding()))
				#now recopying same righs on duplicated entry
				aclFeed = client.GetAclPermissions(entry.resource_id.text)
				for acl in aclFeed.entry:
					if acl.scope.value==oldLogin:
						continue
					if acl.scope.value==newLogin:
						continue
					try:
						LOG.info("        duplicating ACL : "+str(acl.scope.value)+' ('+str(acl.scope.type)+') is '+str(acl.role.value)+' from '+entry.title.text.encode(sys.getfilesystemencoding())+" to "+duplicated_entry.title.text.encode(sys.getfilesystemencoding()))

						newScope = gdata.acl.data.AclScope(value=str(acl.scope.value), type='user')
						newRole = gdata.acl.data.AclRole(value=str(acl.role.value))
						newAcl_entry = gdata.docs.data.Acl(scope=newScope, role=newRole)
						LOG.info("        dup=             : "+str(newAcl_entry.scope.value)+' ('+str(newAcl_entry.scope.type)+') is '+str(newAcl_entry.role.value))
						created_acl_entry = client.Post(newAcl_entry, duplicated_entry.GetAclLink().href)
					except gdata.client.RequestError as error :
						LOG.error('      duplicating ACL failed for '+str(acl.scope.value)+' ('+str(acl.scope.type)+') is '+str(acl.role.value)+' :: '+duplicated_entry.title.text.encode(sys.getfilesystemencoding()))
						logAndProposeAbort(error)
				stats['copied']+=1
			except gdata.client.RequestError as error :
				LOG.error("Copy failed for "+entry.title.text.encode(sys.getfilesystemencoding()))
				logAndProposeAbort(error)
	else:
		LOG.error("Manual copy required for "+entry.title.text.encode(sys.getfilesystemencoding()))
		raw_input("Press a key when done")


def makeReportFile(storeFolder):
	return os.path.join(os.path.abspath(storeFolder), "IMPORTANT-A LIRE-ST.txt")

def logInReportFile(storeFolder, text):
	forceFolder(storeFolder)
	multiplesCollectionsFile = open(makeReportFile(storeFolder), 'a')
	multiplesCollectionsFile.write(text)
	multiplesCollectionsFile.close()

def warnUserOfReportFileIfNecessary(storeFolder):
	reportFile = makeReportFile(storeFolder)
	if os.path.isfile(reportFile):
		LOG.warning ("===== IMPORTANT ===== : some additionnal instructions are stored in "+reportFile)
		LOG.warning ("Please read them carrefully")

def cleanStoreFolder(storeFolder):
	LOG.debug ("Cleaning %s" % storeFolder)
	shutil.rmtree(storeFolder)

def forceFolder(dir):
	if not os.path.exists(dir):
		os.makedirs(dir)
	return dir

def compareDocsEntryOnName(a, b):
        return cmp(a.title.text.lower(), b.title.text.lower())


#http://code.google.com/intl/fr/apis/documents/docs/3.0/developers_guide_python.html#CopyingDocs
if __name__ == '__main__':
	signal.signal(signal.SIGINT, signal_handler)
	print ("Google Docs Transfer v. %s"%__version)
	print ("Python version %s [%s]"% (sys.version, platform.python_version()))
	print ("Developped while migrating documents of standard Google accounts to Google Apps Domain accounts")
	parser = argparse.ArgumentParser(description='Standard exemple : gtransfer.py -l olduser%domain.com@gtempaccount.com -o olduser@domain.com',epilog="Have fun!")
	parser.add_argument('-l', '--login', required=True)
	parser.add_argument('-d', '--directory', help="Where to store you document. If not provided, will use a default localtion based on login and date")
	parser.add_argument('-v', '--verbose', action = 'store_true', dest = 'verbose', default = False,	help = 'increase verbosity')	
	parser.add_argument('-u', '--usage', action="store_true", default=False, help="show help and exit")
	parser.add_argument('-U', '--update', action="store_true", default=False, help="Self update from "+__update_url+" then exit")
	parser.add_argument('-o', '--newOwner', help="New owner of documents", required=True)
	parser.add_argument('--dryRun',action="store_true", default=False,  help="dry run : no copy, no share. Read only!")
	
	args = parser.parse_args()

	if args.usage:
		parser.print_help()
		sys.exit(0)

	setup_logger(args)

	if args.update:
		print ("------------------------------------------------------")
		print ("Automatic update from")
		print ("%s"% __update_url)	
		print ("to ")
		print ("%s"%  __file__)	
		raw_input("Press ENTER to overwrite current version, or CTRL+C to exit now!")
		urllib.urlretrieve(__update_url, __firaw_inputle__)
		print ("New version installed in %s"%__file__)
		sys.exit(0)

	oldOwnerPassword = getpass.getpass("Old (current) owner password ("+args.login+"): ")
	newOwnerPassword = getpass.getpass("New owner password ("+args.newOwner+"): " )
			
	if not args.directory:
		args.directory=str(datetime.date.today())+"_googledocs_transfer_"+args.login
	folder = forceFolder(args.directory)
	LOG.info ("Google Docs Transfer v. %s"%__version)
	LOG.info ("Current date                 : %s" % datetime.date.today())
	LOG.info ("Store folder                 : "+ os.path.abspath(folder))
	if args.verbose==True:
		LOG.info("Verbose Mode                 : ACTIVE")
	if args.dryRun:
		LOG.info("***** Dry Run enabled - No modification will be made to your documents *****")	
	LOG.info("New owner of my documents     : "+args.newOwner)
	LOG.info ("System Encoding              : %s"%sys.getfilesystemencoding())
	LOG.info("===============================================")
	LOG.info("will transfer ALL docs and SHARE of "+args.login+" to account "+args.newOwner)
	LOG.warning("Some informations will be lost during the transfer : here is a non complete list of lost informations : ");
	LOG.warning("versions, comments, revisions, history...");
	LOG.warning("USE WITH EXTREME CAUTION AND AT YOUR OWN RISK !");
	LOG.info("===============================================")
	raw_input("IF YOU HAVE UNDERSTOOD THE RISK AND ARE READY TO START TRANSFER PROCESS, PRESS ENTER TO CONTINUE OR CTRL+C TO CANCEL...")
	LOG.info("TIP : in order to easier the migration process, you should open a page with the google Documents of your old account.")
	LOG.info("      an keep it (screen capture, save as pdf..) : it will be simpler to reorganize docs of the new account after the transfer process")
	LOG.info("===============================================")
	raw_input("Ok, this is the last time I bother you with warnings and others questions. Press ENTER and it will start!")
	LOG.info ("Connecting with OLD google account  : "+args.login)
	oldOwner = gdata.docs.client.DocsClient(source="jgraglia-gtransfer-v1")
	oldOwner.ssl = True 
	oldOwner.http_client.debug = args.verbose
	oldOwner.ClientLogin(args.login, oldOwnerPassword, oldOwner.source);
	LOG.info ("    -> success")

	LOG.info ("Connecting with NEW google account  : "+args.newOwner)
	newOwner = gdata.docs.client.DocsClient(source="jgraglia-gtransfer-v1")
	newOwner.ssl = True 
	newOwner.http_client.debug = args.verbose
	newOwner.ClientLogin(args.newOwner, newOwnerPassword, newOwner.source);
	LOG.info ("    -> success")

	LOG.info ("Retreiving all docs of %s"%args.login)
	oldDocsFeed = oldOwner.GetEverything(uri='/feeds/default/private/full/')
	oldDocsFeed.sort(compareDocsEntryOnName)
	
	doStep0=True
	doStep1=True
	doStep2=True
	doStep3=True
	doStep4=True
	stats = {'removeoldownerright':0, 'addwriter':0, 'copied':0, 'removeAllRightsExceptMine':0}
	sharedDocsCount=0
	ownedDocsCount=0
	if doStep0:
		LOG.info("0/ Listing all docs (owned and shared) in order to perform sanity check among the transfer process")
		LOG.info(str(len(oldDocsFeed))+" docs found")
		for entry in oldDocsFeed:
			if isOwner(oldOwner, entry, args.login):
				ownedDocsCount+=1
			else:
				sharedDocsCount+=1
			LOG.info(str(ownedDocsCount)+" owned / "+str(sharedDocsCount)+" shared..."+entry.title.text.encode(sys.getfilesystemencoding()))
		LOG.info("Please confirm that you currently have "+str(ownedDocsCount)+" owned docs and "+str(sharedDocsCount)+" shared docs for a total of "+str(ownedDocsCount+sharedDocsCount)+" docs in your (old) Google account "+args.login)
		LOG.info("(Collections aren't taken into account in theses figures)")
		LOG.info("If not, this is an error.. Sorry!")
		pressAKeyToContinue()
		
	if doStep1:
		LOG.info("1/ Adding writer rigthts to "+args.newOwner+" (NEW) to ALL documents of "+args.login+" (OLD)")
		pressAKeyToContinue()
		LOG.info("Processing entries...")
		for entry in oldDocsFeed:
			addWriterShareIfNotAlready(oldOwner, entry, args.newOwner)
		LOG.info("Stats:"+str(stats))
		if stats['addwriter'] != (sharedDocsCount+ownedDocsCount) : 
			LOG.error("Only "+str(stats['addwriter'])+" writer ACL added, expecting "+str(sharedDocsCount)+" + "+str(ownedDocsCount)+" = "+str(sharedDocsCount+ownedDocsCount)+" ACL added to new account")
			proposeAbort()
		
	time.sleep(3)
	
	if doStep2:
		LOG.info("2/ Removing "+args.login+" (OLD) rights on ALL non owned documents")
		pressAKeyToContinue()
		LOG.info("Obtaining feed...")
		oldDocsFeed = oldOwner.GetEverything(uri='/feeds/default/private/full/')
		oldDocsFeed.sort(compareDocsEntryOnName)
		processedDocs=0
		for entry in oldDocsFeed:
			if removeAllRightsIfNotOwned(oldOwner, entry, args.login):
				processedDocs+=1
		LOG.info("Stats:"+str(stats))
		if processedDocs != (sharedDocsCount) : 
			LOG.error("Only "+str(processedDocs)+" docs processed, expecting "+str(sharedDocsCount)+" + "+str(ownedDocsCount)+" = "+str(sharedDocsCount+ownedDocsCount))
			proposeAbort()		
			
	time.sleep(3)
		
	if doStep3:
		LOG.info("3/ Copying docs of account "+args.newOwner+" (NEW) currently owned by "+args.login+" (OLD) in order to get ownership (can't transfer ownership among domains!GRrr!)")
		pressAKeyToContinue()
		LOG.info("Obtaining feed...")
		newDocsFeed = newOwner.GetEverything(uri='/feeds/default/private/full/')
		newDocsFeed.sort(compareDocsEntryOnName)

		for entry in newDocsFeed:
			if isOwner(newOwner, entry, args.login):
				LOG.info("Processing doc owned by "+args.login+" : "+entry.title.text.encode(sys.getfilesystemencoding()))
				makeCopy(newOwner, entry, args.login,args.newOwner)
		LOG.info("Stats:"+str(stats))
		if stats['copied'] != ownedDocsCount:
			LOG.error("Only "+str(stats['copied'])+" docs copied in order to gain ownership, expecting "+str(ownedDocsCount)+" docs as listed in step 0")
			proposeAbort()	
		
	time.sleep(3)
	
	if doStep4:
		LOG.info("4/ Removing all remaining rights of "+args.login+" (OLD)")
		pressAKeyToContinue()
		LOG.info("Obtaining feed...")
		oldDocsFeed = oldOwner.GetEverything(uri='/feeds/default/private/full/')
		oldDocsFeed.sort(compareDocsEntryOnName)
		for entry in oldDocsFeed:
			removeAllRightsExceptMine(oldOwner, entry, args.login)
	
	if args.dryRun:
		LOG.info("DRY RUN : no modifications were applied!")
	LOG.info("Stats:"+str(stats))
	LOG.info("Done !")
	LOG.info("Now you can recreate the missing collections in the new acccount ("+args.newOwner+")")
	LOG.info("  You can look at what exists on your old account. This account should contains only collections")
	LOG.info("And after, you can close your old account : ")
	LOG.info("  Go to : https://www.google.com/accounts/ManageAccount whith your OLD account")
	LOG.info("Near 'My products' click on 'Modify' you should be at https://www.google.com/accounts/EditServices")
