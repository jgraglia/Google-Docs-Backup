# coding=<UTF-8>
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
	
# copy from : GDataCopier, http://gdatacopier.googlecode.com/
__bad_chars__ = ['\\', '/', '&', ':']

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
	    print "\n[Interrupted] Bye Bye!"
	    sys.exit(2)


def downloadFeed(client, stdToken, spreadsheetToken, feed, storeFolder, storeFlat, ignoreDualCollections):
	if not feed.entry:
		print ("No entries in feed - Nothing to backup")
	cleanStoreFolder(storeFolder)
	stats = {'doc':0, 'spreadsheet':0, 'impress':0, 'images':0, 'pdf':0, 'other':0}
	for entry in feed.entry:
		ext = ".pdf"
		dl=False
		if entry.GetDocumentType()== "document" :
			ext = ".doc"
			stats['doc']+=1
		elif entry.GetDocumentType() == "presentation":
			ext = ".ppt"
			stats['impress']+=1
		elif entry.GetDocumentType() == "drawing":
			ext =".svg"
			stats['images']+=1
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
		elif entry.GetDocumentType() == "text/xml":
			ext =""
			dl=True			    
			stats['other']+=1			    
		elif entry.GetDocumentType() == "video/mpeg":
			ext =""
			dl=True			    
			stats['other']+=1			    
		else:
			raise Exception("ERROR !!!!!!!! Type de document non géré : "+entry.GetDocumentType())
		print ("---\"%s\" de type %s"%(entry.title.text.encode(sys.getfilesystemencoding()), entry.GetDocumentType()))
		for folder in entry.InFolders():
			print ("   |- "+folder.title)
		filenameToCreate= computeFileNameFor(entry, ext)
		file = computeFileForEntry(client, stdToken, spreadsheetToken, storeFolder, entry, filenameToCreate, storeFlat, ignoreDualCollections)
		
		if dl:
			print ("   |-----> DOWNLOADED")
			print ("           \""+entry.title.text.encode(sys.getfilesystemencoding()) +"\" ["+entry.GetDocumentType()+"] : "+file)
			client.auth_token = stdToken
			client.Download(entry, os.path.abspath(file))
		else:
			print ("   |-----> EXPORTED")
			print ("           \""+entry.title.text.encode(sys.getfilesystemencoding()) +"\" ["+entry.GetDocumentType()+"] : "+file)
			client.auth_token = spreadsheetToken
			client.Export(entry, os.path.abspath(file))
	print ("Stats : "+str(stats))

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
		print ("on essaye d'accéder à '"+folderAsLink.title+"' ("+folderId+") en tant que "+login)
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
		print ("No access to folder "+folderAsLink.title+" : it seems that "+login+" is  not the owner of that folder")
		print ("Error: {0}".format(error))
		return False	

def getFirstCollectionFolderFor(client, stdToken, spreadsheetToken, storeFolder, entry, ignoreDualCollections):
	firstOwnedFolder=None
	for folder in entry.InFolders():
		if isOwnerOfFolder(folder, login, stdToken, spreadsheetToken):
			if firstOwnedFolder!= None:
				if ignoreDualCollections:
					print ("           ATTENTION : "+entry.title.text.encode(sys.getfilesystemencoding())+"' stocké dans (au moins) 2 collections vous appartenant : ceci n'est pas géré! "+" : "+folder.title + " & "+ firstOwnedFolder.title)
					logInReportFile(storeFolder, "\""+entry.title.text.encode('UTF-8')+"\"")
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
			logInReportFile(storeFolder, "\""+folder.title+"\"")
			logInReportFile(storeFolder, ". Vous devrez réimporter manuellement ce fichier dans cette collection partagée.")
			logInReportFile(storeFolder, "\n")
	return firstOwnedFolder

def logInReportFile(storeFolder, text):
	forceFolder(storeFolder)
	multiplesCollectionsFile = open(os.path.join(os.path.abspath(storeFolder), "IMPORTANT-A LIRE-ST.txt"), 'a')
	multiplesCollectionsFile.write(text)
	multiplesCollectionsFile.close()

def cleanStoreFolder(storeFolder):
	print ("Cleaning %s" % storeFolder)
	shutil.rmtree(storeFolder)

def forceFolder(dir):
	if not os.path.exists(dir):
		os.makedirs(dir)
	return dir

if __name__ == '__main__':
	signal.signal(signal.SIGINT, signal_handler)
	print ("Python version %s [%s]"% (sys.version, platform.python_version()))
	print ("Inspired (but with different approach) by GDataCopier, http://gdatacopier.googlecode.com/")
	parser = argparse.ArgumentParser()
	parser.add_argument('-l', '--login')
	parser.add_argument('-p', '--password')
	parser.add_argument('-d', '--directory')
	parser.add_argument('-f', '--flat', action="store_true", default=False)
	parser.add_argument('-i', '--ignore', action="store_true", default=False)
	parser.add_argument('-v', '--verbose', action = 'store_true', dest = 'verbose', default = False,	help = 'increase verbosity')	
	
	args = parser.parse_args()
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
			print ("Le mot de passe est obligatoire")
			sys.exit(1)
			
	if not args.directory:
		args.directory=str(datetime.date.today())+"_googledocs_backup_"+args.login
	folder = forceFolder(args.directory)

	print ("Nous sommes le               : %s" % datetime.date.today())
	print ("Authentification utilisée    : %s:xx" % args.login)
	print ("Répertoire de stockage       : "+ os.path.abspath(folder))
	print ("Stockage dans la collection  : "+ ("NON" if args.flat else "OUI"))
	if args.flat==False:
		print ("Ignorer si multi collections : "+ ("IGNORER" if args.ignore else "LANCER UNE ERREUR"))
	if args.verbose==True:
		print ("Mode debug                   : ACTIVE")
	print ("System Encoding              : %s"%sys.getfilesystemencoding())
	print ("====================================================================")
	print ("ATTENTION : SEUL LES DOCUMENTS APPARTENANT A "+args.login+" SERONT RECUPERES !!!")
	print ("====================================================================")
	raw_input("ENTREE pour continuer, ou CTRL+C pour annuler...")
	print ("Connexion sur le serveur Google...")
	client = gdata.docs.client.DocsClient(source=args.login)
	client.ssl = True 
	client.http_client.debug = False
	client.ClientLogin(args.login, args.password, client.source);
	print ("    -> succès")
	print ("Récupération de la liste des documents appartenant à %s"%args.login)
	feed = client.GetDocList(uri='/feeds/default/private/full/-/mine')
	spreadsheets_client = gdata.spreadsheet.service.SpreadsheetsService()
	spreadsheets_client.ClientLogin(args.login, args.password)
	#client.auth_token = gdata.gauth.ClientLoginToken(spreadsheets_client.GetClientLoginToken())
	login = args.login
	downloadFeed(client, client.auth_token, gdata.gauth.ClientLoginToken(spreadsheets_client.GetClientLoginToken()), feed, folder, args.flat, args.ignore)
	print ("SUCCESS!")
