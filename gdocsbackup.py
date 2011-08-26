#!/usr/bin/env python
# -*- coding: utf-8 -*-
# https://github.com/jgraglia/Google-Docs-Backup
# Usage : python gdocsbackup.py -l xxx@xxxx.com [-p password]

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

# see 	GDataCopier, http://gdatacopier.googlecode.com/
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
        LOG = logging.getLogger("GDOCSBACKUP")
except:
        print "Failed to find logging python modules, please validate the environment"
        exit(1)

__update_url="https://github.com/jgraglia/Google-Docs-Backup/raw/master/gdocsbackup.py"
__version=0.7
	
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


def downloadFeed(client, stdToken, spreadsheetToken, feed, storeFolder, storeFlat, ignoreDualCollections):
	if not feed.entry:
		LOG.info ("No entries in feed - Nothing to backup")
	cleanStoreFolder(storeFolder)
	forceFolder(storeFolder)
	stats = {'doc':0, 'spreadsheet':0, 'impress':0, 'drawings':0, 'images':0, 'pdf':0, 'other':0, 'error':0, 'shared':0}
	for entry in feed.entry:
		ext = ".pdf"
		dl=False

		LOG.info ("---\"%s\" de type %s"%(entry.title.text.encode(sys.getfilesystemencoding()), entry.GetDocumentType()))
		# regular expression to parse RFC3389
		updated_time = datetime.datetime(*map(int, re.split('[^\d]', entry.updated.text)[:-1]))
		date_string = updated_time.strftime('%b %d %Y %H:%M')
		LOG.info ("   |- Timestamp : %s"%date_string)
		#rights
		LOG.info ("   |- Rights :")
		try:
			client.auth_token = stdToken
			aclFeed = client.GetAclPermissions(entry.resource_id.text)
			sharedUserAlreadyWriter=False;
			for acl in aclFeed.entry:
				LOG.info ('   |      |- '+str(acl.scope.value)+' ('+str(acl.scope.type)+') is '+str(acl.role.value))
				if str(acl.scope.value)==args.sharedUser and acl.role.value=="writer":
					sharedUserAlreadyWriter=True

			if not args.sharedUser == None :
				if sharedUserAlreadyWriter:
					LOG.info("      "+str(args.sharedUser)+" is already a writer of that doc. no need to add new ACL ")
				else:
					LOG.info("      Adding 'writer' ACL to : "+args.sharedUser)
					if not args.dryRun:
						newScope = gdata.acl.data.AclScope(value=sharedUser, type='user')
						newRole = gdata.acl.data.AclRole(value='writer')
						newAcl_entry = gdata.docs.data.Acl(scope=newScope, role=newRole)
						created_acl_entry = client.Post(newAcl_entry, entry.GetAclLink().href)

						aclFeed = client.GetAclPermissions(entry.resource_id.text)
						for acl in aclFeed.entry:
							LOG.info ('   |      |- '+str(acl.scope.value)+' ('+str(acl.scope.type)+') is '+str(acl.role.value))
					stats['shared']+=1
		except gdata.client.Unauthorized as error:
			LOG.error("   |  |- CAN'T DISPLAY ACL FOR DOCUMENT : {0}".format(error))

		LOG.info ("   |- Folders :")
		for folder in entry.InFolders():
			LOG.info ("   |      |-"+folder.title)

		if entry.GetDocumentType()== "document" :
			ext = ".doc"
			stats['doc']+=1
		elif entry.GetDocumentType() == "presentation":
			ext = ".ppt"
			stats['impress']+=1
		elif entry.GetDocumentType() == "drawing":
			ext =".svg"
			stats['drawings']+=1
			logInReportFile(storeFolder, ". "+entry.title.text.encode(sys.getfilesystemencoding())+" : Google can export drawing as SVG file, but can't reimport them! This is terrible!\n")
			logInReportFile(storeFolder, "    The only option I'm aware is to share the docs, then make a copy in order to get ownership (because Google can't transfer ownership among domains !! Grrr!!)\n")
		elif entry.GetDocumentType() == "spreadsheet":
			ext =".xls"
			stats['spreadsheet']+=1
		elif entry.GetDocumentType() == "pdf":
			ext =""	
			dl=True				    
			stats['pdf']+=1
		elif entry.GetDocumentType() == "application/vnd.ms-excel":
			ext =""	
			dl=True		
			stats['spreadsheet']+=1		    
		elif entry.GetDocumentType() == "application/msword":
			ext =""	
			dl=True				    
			stats['doc']+=1		    
		elif entry.GetDocumentType() == "application/vnd.ms-powerpoint":
			ext =""	
			dl=True		
			stats['impress']+=1		    
		elif entry.GetDocumentType() == "image/jpeg":
			ext =""
			dl=True	
			stats['images']+=1			    
		elif entry.GetDocumentType() == "image/png":
			ext =""
			dl=True		
			stats['images']+=1			    
		elif entry.GetDocumentType() == "image/svg+xml":
			ext =""
			dl=True		
			stats['images']+=1			    
		elif entry.GetDocumentType() == "text/xml":
			ext =""
			dl=True			    
			stats['other']+=1			    
		elif entry.GetDocumentType() == "video/mpeg":
			ext =""
			dl=True			    
			stats['other']+=1			    
		else:
			if (args.skip):
				LOG.error("   |- content type ("+entry.GetDocumentType()+") is not handled, and skip option is set : DOCUMENT WILL BE SKIPPED ie. NOT SAVED!");
				continue
			else:
				raise Exception("ERROR !!!!!!!! Type de document non géré : "+entry.GetDocumentType())
		filenameToCreate= computeFileNameFor(entry, ext)
		file = computeFileForEntry(client, stdToken, spreadsheetToken, storeFolder, entry, filenameToCreate, storeFlat, ignoreDualCollections)
		
		try:
			if not args.dryRun:
				if dl:
					LOG.info ("   |- > DOWNLOADING...")
					LOG.info ("              \""+entry.title.text.encode(sys.getfilesystemencoding()) +"\" ["+entry.GetDocumentType()+"] : "+file)
					client.auth_token = stdToken
					client.Download(entry, os.path.abspath(file))
				else:
					LOG.info ("   |- > EXPORTING...")
					LOG.info ("              \""+entry.title.text.encode(sys.getfilesystemencoding()) +"\" ["+entry.GetDocumentType()+"] : "+file)
					client.auth_token = spreadsheetToken
					client.Export(entry, os.path.abspath(file))
		except gdata.client.RequestError as error:
			stats['error']+=1
			if args.skip:
				LOG.error ("         ERROR :{0}".format(error))
			else:
				raise
		LOG.info ("   |- >                      ...DONE")
		time.sleep(1)
	LOG.info ("Stats : "+str(stats))
	warnUserOfReportFileIfNecessary(storeFolder)
	return stats

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
		colFolder = os.path.join(os.path.abspath(storeFolder), firstFolder.title.encode(sys.getfilesystemencoding()))
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

def getFirstCollectionFolderFor(client, stdToken, spreadsheetToken, storeFolder, entry, ignoreDualCollections):
	firstOwnedFolder=None
	for folder in entry.InFolders():
		if isOwnerOfFolder(folder, login, stdToken, spreadsheetToken):
			if firstOwnedFolder!= None:
				if ignoreDualCollections:
					LOG.warning ("           ATTENTION : "+entry.title.text.encode(sys.getfilesystemencoding())+"' stocké dans (au moins) 2 collections vous appartenant : ceci n'est pas géré! "+" : "+folder.title + " & "+ firstOwnedFolder.title)
					logInReportFile(storeFolder, "\""+entry.title.text.encode(sys.getfilesystemencoding())+"\"")
					logInReportFile(storeFolder, " se trouvant votre collection ")
					logInReportFile(storeFolder, "\""+firstOwnedFolder.title+"\"")
					logInReportFile(storeFolder, " doit aussi être stocké dans la collection ")
					logInReportFile(storeFolder, "\""+folder.title+"\"")
					logInReportFile(storeFolder, " vous appartenant elle aussi")
					logInReportFile(storeFolder, "\n")
				else:	
					raise Exception("ERROR ! Document '"+entry.title.text.encode(sys.getfilesystemencoding())+"' stocké dans (au moins) 2 collections vous appartenant : ceci n'est pas géré! "+" : "+folder.title + " & "+ firstOwnedFolder.title)
			else:
				firstOwnedFolder = folder;
		else:
			logInReportFile(storeFolder, "\""+entry.title.text.encode(sys.getfilesystemencoding())+"\"")
			logInReportFile(storeFolder, " vous appartient, mais est stocké dans la collection partagée  ")
			logInReportFile(storeFolder, "\""+folder.title.encode(sys.getfilesystemencoding())+"\"")
			logInReportFile(storeFolder, ". Vous devrez réimporter manuellement ce fichier dans cette collection partagée.")
			logInReportFile(storeFolder, "\n")
	return firstOwnedFolder

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

if __name__ == '__main__':
	signal.signal(signal.SIGINT, signal_handler)
	print ("Google Docs Backup v. %s"%__version)
	print ("Python version %s [%s]"% (sys.version, platform.python_version()))
	print ("Inspired (but with different approach) by GDataCopier, http://gdatacopier.googlecode.com/")
	print ("Primary developped when migrating from Google Account to Google Apps Account (many docs of many users to migrate)")
	parser = argparse.ArgumentParser(description='Standard exemple : gdocsbackup.py -l jdoe@gmail.com ',epilog="Have fun!")
	parser.add_argument('-l', '--login')
	parser.add_argument('-p', '--password', help="Warning : the password could be stored in your console history (OS dependant). You'd better not use the option and enter your password when asked by the program")
	parser.add_argument('-d', '--directory', help="Where to store you document. If not provided, will use a default localtion based on login and date")
	parser.add_argument('-f', '--flat', action="store_true", default=False, help="when activated, don't store docs in collections")
	parser.add_argument('-i', '--ignore', action="store_true", default=False)
	parser.add_argument('-v', '--verbose', action = 'store_true', dest = 'verbose', default = False,	help = 'increase verbosity')	
	parser.add_argument('-u', '--usage', action="store_true", default=False, help="show help and exit")
	parser.add_argument('-U', '--update', action="store_true", default=False, help="Self update from "+__update_url+" then exit")
	parser.add_argument('-s', '--skip', action="store_true", default=False, help="Skip unknown content type (data will NOT be copied!")
	parser.add_argument('-D', '--debug', action="store_true", default=False, help="Active full debug")
	parser.add_argument('-S', '--sharedUser', help="Google account to share all MY docs with")
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
		urllib.urlretrieve(__update_url, __file__)
		print ("New version installed in %s"%__file__)
		sys.exit(0)

	if not args.login:
		#python 3 : input, python 2.x : raw_input
		if sys.version_info >= (3, 0):
			args.login = input("Username [%s]: " % getpass.getuser())
		else:
			args.login = raw_input("Username [%s]: " % getpass.getuser())
		if not args.login:
			args.login=getpass.getuser()
	if not args.password:
		args.password=getpass.getpass()
		if not args.password:
			print ("Password is mandatory")
			sys.exit(1)
			
	if not args.directory:
		args.directory=str(datetime.date.today())+"_googledocs_backup_"+args.login
	folder = forceFolder(args.directory)
	LOG.info ("Google Docs Backup v. %s"%__version)
	LOG.info ("Nous sommes le               : %s" % datetime.date.today())
	LOG.info ("Authentification utilisée    : %s:xx" % args.login)
	LOG.info ("Répertoire de stockage       : "+ os.path.abspath(folder))
	LOG.info ("Stockage dans la collection  : "+ ("NON" if args.flat else "OUI"))
	if args.flat==False:
		LOG.info ("Ignorer si multi collections : "+ ("IGNORER" if args.ignore else "LANCER UNE ERREUR"))
	if args.verbose==True:
		LOG.info("Verbose Mode                 : ACTIVE")
	if args.debug==True:
		LOG.info("Debug Mode                   : ACTIVE")
	if args.skip==True:
		LOG.info("Skip unknown content         : ACTIVE")
	if not args.sharedUser==None:
		LOG.info("Be careful, all you OWNED DOCUMENTS will be shared with '"+args.sharedUser+"' - Please confirm (y) or die")
		confirmShared = raw_input("Confirm that you understand that your private doc will be shared with '"+args.sharedUser+"' google user (y|Y) or die : ")
		if not confirmShared.lower() == "y" and not confirmShared.lower() == "yes":
			exit(1)
	if args.dryRun:
		LOG.info("Dry Run enabled - No modification will be made to your documents")	
	LOG.info ("System Encoding              : %s"%sys.getfilesystemencoding())
	LOG.info ("====================================================================")
	LOG.info ("ATTENTION : SEUL LES DOCUMENTS APPARTENANT A "+args.login+" SERONT RECUPERES !!!")
	LOG.info ("====================================================================")
	raw_input("ENTREE pour continuer, ou CTRL+C pour annuler...")
	LOG.info ("Connexion sur le serveur Google...")
	client = gdata.docs.client.DocsClient(source="jgraglia-gdocsbackup-v1")
	client.ssl = True 
	client.http_client.debug = args.debug
	client.ClientLogin(args.login, args.password, client.source);
	LOG.info ("    -> succès")
	LOG.info ("Récupération de la liste des documents appartenant à %s"%args.login)
	feed = client.GetDocList(uri='/feeds/default/private/full/-/mine')
	spreadsheets_client = gdata.spreadsheet.service.SpreadsheetsService()
	spreadsheets_client.ClientLogin(args.login, args.password)
	#client.auth_token = gdata.gauth.ClientLoginToken(spreadsheets_client.GetClientLoginToken())
	login = args.login
	stats = downloadFeed(client, client.auth_token, gdata.gauth.ClientLoginToken(spreadsheets_client.GetClientLoginToken()), feed, folder, args.flat, args.ignore)
	LOG.info ("Storing log in backup folder (contains important ownership and share infos, that you could use when re-importing documents)")
	shutil.copy2('output.log', folder+"/output.log")
	LOG.info (os.path.abspath(folder))
	if not args.sharedUser == None:
		LOG.info(str(stats['shared'])+" document(s) where shared with user "+str(args.sharedUser))
	if stats['error']>0:
		LOG.error("ERROR ! "+str(stats['error'])+" error(s) occured, some document aren't stored. See output.log for details")
	else:
		LOG.info ("SUCCESS !")
