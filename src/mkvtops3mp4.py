#!/usr/bin/python
#
#
# Copyright (c) 2008, Reid Nichol <oddmanout@orthogonalspace.ca>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or
# without modification, are permitted provided that the following
# conditions are met:
#
#    * Redistributions of source code must retain the above
#      copyright notice, this list of conditions and the following
#      disclaimer.
#    * Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      disclaimer in the documentation and/or other materials
#      provided with the distribution.
#    * Neither the name of Reid Nichol nor the names of its
#      contributors may be used to endorse or promote products
#      derived from this software without specific prior written
#      permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#

# NOTE:
# /usr/bin/python is used as that is the stock binary that comes with
# OSX and it is the binary in which I have tested and the target audience
# will have.  It is also used so that if the user has installed Python
# through MacPorts that the "correct" one will be used.  If this isn't
# wanted, feel free to change it to the "standard" #!:
#
# /usr/bin/evn python
#

from Tkinter import *
import tkFileDialog, tkMessageBox

import os, sys, math, string
import popen2, threading
import re
import Queue

rootWin           = None

status            = []
statusLabel       = None
statusDisplay     = 0
statusDecodeLock  = threading.Lock()
statusDecode      = 0
guiUpdateTimer    = None
file              = None
fileInput         = None
fileList          = []
fileSize          = None
fileSizeLabel     = None
piecesMenu        = None
numPieces         = None
sizePerPieceLabel = None
sizePerPiece      = None
bitrate           = None
bitrateMenu       = None
channels          = None
goButton          = None
browseButton      = None

videoTrack        = None

workerThread      = None

statusQueue       = None


# DEV NOTE: Put buttons into one variable
# buttons = {}
# buttons['goButton'] = {'button': None, 'activate': 1}
#
# button being the actual button
# activate being whether it should be activated or not
#          for selection (peiceds is only this way if
#          the file is above a certain limit).

# DEV NOTE: Add debug mode so that when issues come in
#           we can get the output easily.

# DEV NOTE: Get rid of unused global vars

# DEV NOTE: Implement large file support.


def mp4AddAudioOptimise():
	global file

	try:
		p = popen2.Popen4('mp4creator -c ' + os.path.dirname(file) + os.sep + 'audio.aac -interleave -optimize ' + os.path.dirname(file) + os.sep + 'file.mp4')

		for line in p.fromchild.readlines():
			if re.compile("command\ not\ found").search(line):
				changeDecodeStatus(-9, "Couldn't find executable: mp4creator")
				raise

		p.wait()

		return 1
	except:
		pass

	return -1

def mp4AddHint():
	global file

	try:
		p = popen2.Popen4('mp4creator -hint=1 ' + os.path.dirname(file) + os.sep + 'file.mp4')

		for line in p.fromchild.readlines():
			if re.compile("command\ not\ found").search(line):
				changeDecodeStatus(-8, "Couldn't find executable: mp4creator")
				raise

		p.wait()

		return 1
	except:
		pass

	return -1

def mp4AddVideo():
	global file, videoTrack

	try:
		p = popen2.Popen4('mp4creator -create=' + os.path.dirname(file) + os.sep + 'video.h264 -rate=' + str(videoTrack['fps']) + ' ' + os.path.dirname(file) + os.sep + 'file.mp4')

		for line in p.fromchild.readlines():
			if re.compile("command\ not\ found").search(line):
				changeDecodeStatus(-7, "Couldn't find executable: mp4creator")
				raise

			if re.compile("failed\ assertion.+m_size").search(line):
				changeDecodeStatus(-7, 'Video track too large for mp4.  Split output into more pieces. ')
				raise# Exception('Video track too large for mp4.  Split output into more pieces. ')

		p.wait()

		# video is no longer needed
		removeVideo()

		return 1
	except:
		pass

	return -1

def getAudio(recurs=0):
	global file, channels, bitrate

	changeCodec = 0
	acodec = ['libfaac', 'faac', 'aac']

	try:
		chnls = channels.get()
		if chnls == '5.1':
			chnls = '6'

		p = popen2.Popen4('ffmpeg -i ' + file + ' -vn -ac ' + chnls + ' -acodec ' + acodec[recurs] + ' -ab ' + bitrate.get() + 'k ' + os.path.dirname(file) + os.sep + 'audio.aac')

		for line in p.fromchild.readlines():
			if re.compile("command\ not\ found").search(line):
				changeDecodeStatus(-6, "Couldn't find executable: ffmpeg")
				raise

			if re.compile("^Unknown\ codec\ \'" + acodec[recurs] + "\'").match(line):
				# run through all lines and wait() before lauching
				# the other process to prevent zombies
				changeCodec = 1

		p.wait()

		# If not the default codec name, give the other one
		# as first reported by 'Raoul' on (change to libfaac):
		# http://oddmanout.wordpress.com/2008/01/26/converting-an-mkv-h264-file-to-ps3-mp4-without-re-encoding-on-mac-os-x/
		#
		# And from nabstersblog we get another codec name (change to faac)
		# http://nabstersblog.blogspot.com/2008/09/notes-on-converting-h264-to-ps3.html
		#
		# One has to wonder what the ffmpeg people are thinking not having
		# a consistent name for the same output across versions/platforms.

		# we got an codec error
		if changeCodec:
			recurs += 1
			if recurs < len(acodec):
				# if 1, the try the other one
				return getAudio(recurs)
			else:
				# otherwise both failed and we quit
				changeDecodeStatus(-6, "Coudn't find appropriate audio codec.")
				raise# Exception("Coudn't find appropriate audio codec.")
		return 1
	except:
		pass

	return -1

def correctProfile():
	global file

	import struct
	levelString = struct.pack('b', int('29', 16))

	fp = open(os.path.dirname(file) + os.sep + 'video.h264', 'r+b')
	if not fp:
		changeDecodeStatus(-5, "Couldn't open extracted video to correct profile.")
		return -1

	fp.seek(7)
	fp.write(levelString)
	fp.close()

	return 1

def extractVideo():
	global videoTrack, file

	try:
		p = popen2.Popen4('mkvextract tracks ' + file + ' ' + str(videoTrack['number']) + ':' + os.path.dirname(file) + os.sep + 'video.h264 > /dev/null')


		for line in p.fromchild.readlines():
			if re.compile("command\ not\ found").search(line):
				changeDecodeStatus(-4, "Couldn't find executable: mkvextract")
				raise

		p.wait()

		return 1
	except:
		pass

	return -1


def getMKVInfo():
	global videoTrack, file

	track = {'video': 0, 'audio': 0}

	# to make sure that two or more runs in
	# row run as expected i.e. we don't want
	# the previous runs success to impact
	# this runs possible failure
	videoTrack = None

	try:
		p = popen2.Popen4('mkvinfo ' + file)
		for line in p.fromchild.readlines():
			if re.compile("command\ not\ found").search(line):
				changeDecodeStatus(-3, "Couldn't find executable: mkvinfo")
				raise

			if re.compile("^\|\ \+\ A\ track").match(line):
				if track['video'] == 1:
					videoTrack = track
				track = {'video': 0, 'audio': 0}
				continue
			m = re.compile("^\|\ \ \+\ Track\ number\:\ (\d+)").match(line)
			if m:
				track['number'] = m.group(1)
				continue

			m = re.compile("^\|\ \ \+\ Track\ type\:\ (\S+)").match(line)
			if m:
				if m.group(1) == 'video':
					track['video'] = 1
					track['audio'] = 0
					continue
				if m.group(1) == 'audio':
					track['video'] = 0
					track['audio'] = 1

			m = re.compile("^\|\ \ \+\ Default\ duration\:\ \d+\.\d+\S+\ \((\d+)\.(\d+)\ fps").match(line)
			if m and m.group(1) and m.group(2):
				track['fps'] = float(str(m.group(1)) + '.' + str(m.group(2)))
				continue

			m = re.compile("^\|\ \ \+\ Codec\ ID\:\ (\S+\/\S+\/\S+)").match(line)
			if m and m.group(1):
				if track['video'] == 1 and m.group(1) != 'V_MPEG4/ISO/AVC':
					changeDecodeStatus(-2, 'Bad video format: ' + m.group(1))
					raise# Exception('Bad video format: ' + m.group(1))

				track['codecID'] = m.group(1)

		p.wait()

		# if the video track is the last track, we
		# need to catch that
		if videoTrack == None and track['video'] == 1:
			videoTrack = track

		if videoTrack == None:
			changeDecodeStatus(-2, 'No video track found.  It might be missing or of an inappropriate type.')
			raise# Exception('No video track found')

		return 1
	except:
		pass

	return -1

def splitFile():
	global fileInput, fileList, sizePerPiece, numPieces

	# don't split if only doing one piece
	if int(numPieces.get()) == 1:
		fileList.append(fileInput.get())
		return 1

	try:
		splitMKV = os.path.splitext(fileInput.get())[0] + '-split.mkv'
		p = popen2.Popen4('mkvmerge -o ' + splitMKV + ' --split ' + str(sizePerPiece) + 'M ' + fileInput.get())
		for line in p.fromchild.readlines():
			if re.compile("command\ not\ found").search(line):
				changeDecodeStatus(-3, "Couldn't find executable: mkvinfo")
				raise

			m = re.compile('^The\ file\ \'(.*)\'\ has\ been\ opened\ for\ writing\.$').match(line)
			if m and m.group(1):
				fileList.append(m.group(1))

		return 1
	except:
		pass

	return -1


def changeDecodeStatus(old, new):
	global statusQueue

	statusQueue.put((old, new))


def checkDecodeStatus():
	global rootWin, statusQueue, status, goButton, browseButton, bitrateMenu

	try:
		stat = statusQueue.get(0)
		old = stat[0]
		new = stat[1]

		# error code
		if (old < 0):
			errorDecoding(new)

			# order is, 1) report error, 2) update status
			# so one more is coming
			rootWin.after(1000, checkDecodeStatus)
			return

		tmpText = status[old]['text']
		tmpText = string.replace(tmpText, '*', ' ', 1)
		status[old]['text'] = tmpText
		tmpText = status[new]['text']
		tmpText = string.replace(tmpText, ' ', '*', 1)
		status[new]['text'] = tmpText

		if not (new == 9 or new == 0):
			# Once per second should be enough and not
			# waste resources.
			rootWin.after(1000, checkDecodeStatus)
		else:
			# re-enable the buttons after the run has
			# completed
			goButton['state'] = NORMAL
			browseButton['state'] = NORMAL
			bitrateMenu['state'] = NORMAL
	except:
		rootWin.after(1000, checkDecodeStatus)



def errorDecoding(msg):
	tkMessageBox.showerror(title='Premature End Of Run', message=msg)

def removeAudio():
	global file

	if os.path.exists(os.path.dirname(file) + os.sep + 'audio.aac'):
		os.remove(os.path.dirname(file) + os.sep + 'audio.aac')


def removeVideo():
	global file

	if os.path.exists(os.path.dirname(file) + os.sep + 'video.h264'):
		os.remove(os.path.dirname(file) + os.sep + 'video.h264')


def renameMP4():
	global file

	if os.path.exists(os.path.dirname(file) + os.sep + 'file.mp4'):
		old = os.path.dirname(file) + os.sep + 'file.mp4'
		new = os.path.splitext(file)[0] + '.mp4'
		os.rename(old, new)

# This function is ONLY for cleaning up
# after converting a video that was SPLIT.
# NEVER use otherwise!
def removeMKV():
	global file

	if os.path.exists(file):
		os.remove(file)


def cleanUp():
	global fileList

	removeAudio()
	removeVideo()
	renameMP4()

	if len(fileList) > 1:
		removeMKV()


def startDecoding():
	global statusQueue, fileInput, fileList, file
	i = 0

	# Make the working directory the directory where
	# file is and save the one that we started with.
	# This will be reset in cleanUp() upon end of
	# run for whatever reason.
	cwd = os.getcwd()
	os.chdir(os.path.dirname(fileInput.get()))

	# reset our list in case the user is going
	# for a second (or more) time(s)
	fileList = []

	changeDecodeStatus(0, 1)
	if splitFile() < 0:
		changeDecodeStatus(1, 0)
		cleanUp()
		return

	i = 1
	changeDecodeStatus(1, 2)
	while i <= len(fileList):
		file = fileList[i - 1]
		statusLabel['text'] = 'Status (%d/%d):'%(i, len(fileList))

		if getMKVInfo() < 0:
			changeDecodeStatus(2, 0)
			cleanUp()
			return

		changeDecodeStatus(2, 3)
		if extractVideo() < 0:
			changeDecodeStatus(3, 0)
			cleanUp()
			return

		changeDecodeStatus(3, 4)
		if correctProfile() < 0:
			changeDecodeStatus(4, 0)
			cleanUp()
			return

		changeDecodeStatus(4, 5)
		if getAudio() < 0:
			changeDecodeStatus(5, 0)
			cleanUp()
			return

		changeDecodeStatus(5, 6)
		if mp4AddVideo() < 0:
			changeDecodeStatus(6, 0)
			cleanUp()
			return

		changeDecodeStatus(6, 7)
		if mp4AddHint() < 0:
			changeDecodeStatus(7, 0)
			cleanUp()
			return

		changeDecodeStatus(7, 8)
		if mp4AddAudioOptimise() < 0:
			changeDecodeStatus(8, 0)
			cleanUp()
			return

		cleanUp()

		# if we aren't on the last piece,
		# we go back and do the other
		# peice(s)
		if len(fileList) != i:
			changeDecodeStatus(8, 2)

		i += 1

	changeDecodeStatus(8, 9)
	statusLabel['text'] = 'Status:'

	os.chdir(cwd)

def decode():
	global workerThread, goButton, browseButton

	if not workerThread or not workerThread.isAlive():
		goButton['state'] = DISABLED
		browseButton['state'] = DISABLED
		bitrateMenu['state'] = DISABLED

		workerThread = threading.Thread(target=startDecoding)
		workerThread.start()

		checkDecodeStatus()


# arg is required but not necessary to use
def calcSizePerPiece(arg):
	global numPieces, fileSize, sizePerPieceLabel, statusLabel, sizePerPiece

	numP = numPieces.get()
	sizeP = float(fileSize)/float(numP)

	post = ['KB', 'MB', 'GB', 'TB']

	# so we tweak that to human readable
	tmpSize = float(math.ceil(sizeP))
	# so we have the size per peice in MB
	sizePerPiece = int(float(math.ceil( ( tmpSize / 1024.0 ) / 1024.0 )))
	for p in post:
		tmpSize = tmpSize/1024.0
		if tmpSize < 1024.0:
			sizePerPieceLabel['text'] = 'Size Per Piece: %0.2f %s'%(tmpSize, p)
			break

	statusLabel['text'] = 'Status (0/%d):'%int(numP)

def checkForLargeFile():
	global fileSize, piecesMenu, numPieces

	fourGB = 1024*1024*1024*4
	if fileSize > fourGB:
		# we must set the number of pieces
		# to output.  start with 2 pieces
		i = 2
		while i*fourGB < fileSize:
			i += 1

		numPieces.set(str(i))
		piecesMenu['state'] = NORMAL

		tkMessageBox.showinfo(title='Number of Pieces', message='We have set the number of pieces to output to '+str(i)+' to accomidate the 4GB limit of the PS3.  You may change it to your liking if you wish.  But, doing so may create problems.')
	else:
		# make sure we set things ok
		numPieces.set('1')
		#piecesMenu['stat'] = DISABLED
		piecesMenu['stat'] = NORMAL

def setFileSize():
	global fileInput, fileSize, fileSizeLabel
	post = ['KB', 'MB', 'GB', 'TB']

	# statinfo.st_size in bytes
	statinfo = os.stat(fileInput.get())
	fileSize = statinfo.st_size

	# so we tweak that to human readable
	tmpSize = float(fileSize)
	for p in post:
		tmpSize = tmpSize/1024.0
		if tmpSize < 1024:
			fileSizeLabel['text'] = 'Size: %0.2f %s'%(tmpSize, p)
			break

def setFile():
	global fileInput
	tmp = tkFileDialog.askopenfilename(filetypes=[('Matroska Video Files', '*.mkv')])

	if tmp != "":
		# it won't allow writing otherwise
		fileInput['stat'] = NORMAL
		fileInput.delete(0, END)
		fileInput.insert(INSERT, tmp)
		fileInput['stat'] = DISABLED

		setFileSize()
		checkForLargeFile()
		calcSizePerPiece(-1)

def makeGUI():
	global rootWin, status, statusLabel, file, fileInput, fileSizeLabel, piecesMenu, numPieces, bitrate, bitrateMenu, goButton, browseButton, sizePerPieceLabel, channels, statusLabel

	# input file portion
	fileEntryFrame = Frame(rootWin)

	Label(fileEntryFrame, text='File: ').pack(side=LEFT)
	fileInput = Entry(fileEntryFrame, width=72, state=DISABLED)
	fileInput.pack(side=LEFT)
	browseButton = Button(fileEntryFrame, text='browse', command=setFile)
	browseButton.pack(side=LEFT)

	fileEntryFrame.pack(side=TOP, fill=X)


	# size/num pieces portion
	# needs to be split into two parts to get
	# the desired layout
	sizePiecesFrame = Frame(rootWin)

	sizePiecesFrameA = Frame(sizePiecesFrame)
	fileSizeLabel = Label(sizePiecesFrameA, text="Size: ")
	fileSizeLabel.pack(side=LEFT)
	Label(sizePiecesFrameA, text="Pieces").pack(side=RIGHT)
	numPieces = StringVar()
	piecesMenu = OptionMenu(sizePiecesFrameA, numPieces, '1', '2', '3', '4', '5', command=calcSizePerPiece)
	#piecesMenu['state'] = DISABLED
	piecesMenu['state'] = NORMAL
	numPieces.set('1')
	piecesMenu.pack(side=RIGHT)
	Label(sizePiecesFrameA, text="Split Into ").pack(side=RIGHT)
	sizePiecesFrameA.pack(side=TOP, fill=X)

	sizePiecesFrameB = Frame(sizePiecesFrame)
	sizePerPieceLabel = Label(sizePiecesFrameB, text="Size Per Piece: ")
	sizePerPieceLabel.pack(side=LEFT)
	sizePiecesFrameB.pack(side=BOTTOM, fill=X)

	sizePiecesFrame.pack(side=TOP, fill=X)


	# audio portion
	audioFrame = Frame(rootWin)

	audioFrameA = Frame(audioFrame)
	Label(audioFrameA, text='Audio:').pack(side=LEFT, fill=X)
	audioFrameA.pack(side=TOP, fill=X)

	audioFrameB = Frame(audioFrame)
	Label(audioFrameB, text='Bit Rate: ').pack(side=LEFT, fill=X)
	bitrate = StringVar()
	bitrateMenu = OptionMenu(audioFrameB, bitrate, '64', '128', '256', '320')
	bitrate.set('64')
	bitrateMenu.pack(side=LEFT, fill=X)
	Label(audioFrameB, text='kbps').pack(side=LEFT, fill=X)

	channels = StringVar()
	channelsMenu = OptionMenu(audioFrameB, channels, '1', '2', '5.1')
	channelsMenu['state'] = DISABLED
	channels.set('2')
	channelsMenu.pack(side=RIGHT, fill=X)
	Label(audioFrameB, text='Channels: ').pack(side=RIGHT, fill=X)
	audioFrameB.pack(side=BOTTOM, fill=X)

	audioFrame.pack(side=TOP, fill=X)


	# status portion
	statusFrame = Frame(rootWin)

	statusFrame0 = Frame(statusFrame)
	statusLabel = Label(statusFrame0, text='Status:')
	statusLabel.pack(side=LEFT, fill=X)
	statusFrame0.pack(side=TOP, fill=X)

	statusFrameA = Frame(statusFrame)
	status.append(Label(statusFrameA, text='* 0: Stopped'))
	statusFrameA.pack(side=TOP, fill=X)

	statusFrameB = Frame(statusFrame)
	status.append(Label(statusFrameB, text='  1: Splitting'))
	statusFrameB.pack(side=TOP, fill=X)

	statusFrameC = Frame(statusFrame)
	status.append(Label(statusFrameC, text='  2: Getting MKV Info'))
	statusFrameC.pack(side=TOP, fill=X)

	statusFrameD = Frame(statusFrame)
	status.append(Label(statusFrameD, text='  3: Extracting Video'))
	statusFrameD.pack(side=TOP, fill=X)

	statusFrameE = Frame(statusFrame)
	status.append(Label(statusFrameE, text='  4: Correcting Profile'))
	statusFrameE.pack(side=TOP, fill=X)

	statusFrameF = Frame(statusFrame)
	status.append(Label(statusFrameF, text='  5: Extracting/Converting Audio'))
	statusFrameF.pack(side=TOP, fill=X)

	statusFrameG = Frame(statusFrame)
	status.append(Label(statusFrameG, text='  6: Adding Video To MP4'))
	statusFrameG.pack(side=TOP, fill=X)

	statusFrameH = Frame(statusFrame)
	status.append(Label(statusFrameH, text='  7: Hinting Video'))
	statusFrameH.pack(side=TOP, fill=X)

	statusFrameI = Frame(statusFrame)
	status.append(Label(statusFrameI, text='  8: Adding Audio And Optimising MP4'))
	statusFrameI.pack(side=TOP, fill=X)

	statusFrameJ = Frame(statusFrame)
	status.append(Label(statusFrameJ, text='  9: Done'))
	statusFrameJ.pack(side=TOP, fill=X)

	for i in status:
		i.pack(side=LEFT, fill=X)

	statusFrame.pack(side=TOP, fill=X)


	# go button
	goFrame = Frame(rootWin)
	goButton = Button(goFrame, text='Start', command=decode)
	goButton.pack(side=BOTTOM)
	goFrame.pack(side=BOTTOM, fill=X)


# Code from Dave Opstad to hide the Console window that
# py2app annoyingly thinks is so necessary.
#
# http://coding.derkeiler.com/Archive/Python/comp.lang.python/2006-10/msg00414.html
def hideConsole():
	global rootWin

	if (sys.platform != "win32") and hasattr(sys, 'frozen'):
		rootWin.tk.call('console', 'hide')



if __name__ == '__main__':
	global rootWin, statusQueue

	statusQueue = Queue.Queue()

	rootWin = Tk()
	rootWin.title("MKV to PS3 MP4")
	makeGUI()

#	debuging needs the console
#	hideConsole()

	rootWin.mainloop()

