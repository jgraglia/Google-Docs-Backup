# coding=<UTF-8>
# il faut python 2.x : http://www.python.org/getit/
# et Google Data API 2.0.14+ : http://code.google.com/p/gdata-python-client/downloads/list
# https://github.com/jgraglia/Google-Docs-Backup
# Usage : python gdocsbackup.py -l xxx@xxxx.com [-p password]
 
import gdata.spreadsheet.service
import gdata.docs.service
import gdata.docs.client
import sys
import argparse
from types import NoneType
import getpass
import os
import datetime
import platform

def downloadFeed(client, stdToken, spreadsheetToken, feed, storeFolder, storeFlat):
	if not feed.entry:
			print 'No entries in feed - Nothing to backup!\n'
	for entry in feed.entry:
		ext = ".pdf"
		dl=False
		if entry.GetDocumentType()== "document" :
			ext = ".doc"
		elif entry.GetDocumentType() == "presentation":
			ext = ".ppt"
		elif entry.GetDocumentType() == "drawing":
		    ext =".svg"
		elif entry.GetDocumentType() == "spreadsheet":
		    ext =".xls"	
		elif entry.GetDocumentType() == "image/jpeg":
			ext =".jpg"
			dl=True				    
		elif entry.GetDocumentType() == "image/png":
			ext =".png"
			dl=True			    
		elif entry.GetDocumentType() == "text/xml":
			ext =".xml"
			dl=True			    
		else:
			raise Exception("ERROR !!!!!!!! Type de document non géré : "+entry.GetDocumentType())
		filenameToCreate= computeFileNameFor(entry, ext)
		if storeFlat == False:
			firstFolder=getFirstCollectionFolderFor(entry)
			if firstFolder==None:
				file = os.path.join(os.path.abspath(storeFolder), filenameToCreate)
			else:				
				colFolder = os.path.join(os.path.abspath(storeFolder), firstFolder.title)
				forceFolder(colFolder)
				file = os.path.join(os.path.abspath(colFolder), filenameToCreate)
		else:
			file = os.path.join(os.path.abspath(storeFolder), filenameToCreate)
		if dl:
			print "DOWNLOAD du document \""+entry.title.text.encode('UTF-8') +"\" de type \""+entry.GetDocumentType()+"["+ext+ "]\" vers le fichier "+file
			client.auth_token = stdToken
			client.Download(entry, os.path.abspath(file))

		else:
			print "EXPORT   du document \""+entry.title.text.encode('UTF-8') +"\" de type \""+entry.GetDocumentType()+"["+ext+ "]\" vers le fichier "+file
			client.auth_token = spreadsheetToken
			client.Export(entry, os.path.abspath(file))

def computeFileNameFor(entry, ext):
	return entry.title.text.encode('UTF-8').replace('\\', '_').replace('/', '_').replace('$', '_')+ext

def getFirstCollectionFolderFor(entry):
	firstFolder=None
	for folder in entry.InFolders():
		if firstFolder!=None:
			# not handled... yet!
			raise Exception("ERROR ! Document '"+entry.title.text.encode('UTF-8')+"' stocké dans (au moins) 2 collections : ceci n'est pas géré! "+" : "+folder.title + " & "+ firstFolder.title)
		firstFolder = folder;
	return firstFolder

def forceFolder(dir):
	if not os.path.exists(dir):
		os.makedirs(dir)
	return dir

if __name__ == '__main__':
	print "Python version "+ sys.version+" ["+platform.python_version()+"]"
	parser = argparse.ArgumentParser()
	parser.add_argument('-l', '--login')
	parser.add_argument('-p', '--password')
	parser.add_argument('-d', '--directory')
	parser.add_argument('-f', '--flat', action="store_true", default=False)
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
			print "Le mot de passe est obligatoire"
			sys.exit(1)
			
	if not args.directory:
		args.directory=str(datetime.date.today())+"_googledocs_backup_"
	folder = forceFolder(args.directory)

	print "Nous sommes le              : ",datetime.date.today()
	print "Authentification utilisée   : " + args.login+":xxx"
	print "Répertoire de stockage      : "+ os.path.abspath(folder)
	print "Stockage dans la collection : "+ ("NON" if args.flat else "OUI")
	print "===================================================================="
	print "ATTENTION : SEUL LES DOCUMENTS APPARTENANT A "+args.login+" SERONT RECUPERES !!!"
	print "===================================================================="
	raw_input("ENTREE pour continuer, ou CTRL+C pour annuler...")
	print "Connexion sur le serveur Google..."
	client = gdata.docs.client.DocsClient(source=args.login)
	client.ssl = True 
	client.http_client.debug = False
	client.ClientLogin(args.login, args.password, client.source);
	print "    -> succès"
	print "Récupération de la liste des documents appartenant à "+args.login
	feed = client.GetDocList(uri='/feeds/default/private/full/-/mine')
	spreadsheets_client = gdata.spreadsheet.service.SpreadsheetsService()
	spreadsheets_client.ClientLogin(args.login, args.password)
	#client.auth_token = gdata.gauth.ClientLoginToken(spreadsheets_client.GetClientLoginToken())
	downloadFeed(client, client.auth_token, gdata.gauth.ClientLoginToken(spreadsheets_client.GetClientLoginToken()), feed, folder, args.flat)
	print "    -> SUCCESS"
