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

import os, math, string
import popen2, threading
import re
import Queue

rootWin           = None

status            = []
statusDisplay     = 0
statusDecodeLock  = threading.Lock()
statusDecode      = 0
guiUpdateTimer    = None
file              = None
fileSize          = None
fileSizeLabel     = None
piecesMenu        = None
numPieces         = None
sizePerPieceLabel = None
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
		p = popen2.Popen4('mp4creator -c ' + os.path.dirname(file.get()) + os.sep + 'audio.aac -interleave -optimize ' + os.path.dirname(file.get()) + os.sep + 'file.mp4')

		p.fromchild.readlines()
		p.wait()

		return 1
	except:
		pass

	return -1

def mp4AddHint():
	global file

	try:
		p = popen2.Popen4('mp4creator -hint=1 ' + os.path.dirname(file.get()) + os.sep + 'file.mp4')

		p.fromchild.readlines()
		p.wait()

		return 1
	except:
		pass

	return -1

def mp4AddVideo():
	global file, videoTrack

	try:
		p = popen2.Popen4('mp4creator -create=' + os.path.dirname(file.get()) + os.sep + 'video.h264 -rate=' + str(videoTrack['fps']) + ' ' + os.path.dirname(file.get()) + os.sep + 'file.mp4')

		for line in p.fromchild.readlines():
			if re.compile("failed\ assertion.+m_size").search(line):
				raise Exception('Video track too large for mp4.  Split output into more pieces. ')

		p.wait()

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

		p = popen2.Popen4('ffmpeg -i ' + file.get() + ' -vn -ac ' + chnls + ' -acodec ' + acodec[recurs] + ' -ab ' + bitrate.get() + 'k ' + os.path.dirname(file.get()) + os.sep + 'audio.aac')

		for line in p.fromchild.readlines():
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
				raise Exception("Coudn't find appropriate audio codec.")
		return 1
	except:
		pass

	return -1

def correctProfile():
	global file

	import struct
	levelString = struct.pack('b', int('29', 16))

	fp = open(os.path.dirname(file.get()) + os.sep + 'video.h264', 'r+b')
	if not fp:
		return -1

	fp.seek(7)
	fp.write(levelString)
	fp.close()

	return 1

def extractVideo():
	global videoTrack, file

	try:
		p = popen2.Popen3('mkvextract tracks ' + file.get() + ' ' + str(videoTrack['number']) + ':' + os.path.dirname(file.get()) + os.sep + 'video.h264 > /dev/null')


		p.fromchild.readlines()
		p.wait()

		return 1
	except:
		pass

	return -1


def getMKVInfo():
	global videoTrack

	track = {'video': 0, 'audio': 0}

	# to make sure that two or more runs in
	# row run as expected i.e. we don't want
	# the previous runs success to impact
	# this runs possible failure
	videoTrack = None

	try:
		p = popen2.Popen3('mkvinfo ' + file.get())
		for line in p.fromchild.readlines():
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
					raise Exception('Bad video format: ' + m.group(1))

				track['codecID'] = m.group(1)

		p.wait()

		# if the video track is the last track, we
		# need to catch that
		if videoTrack == None and track['video'] == 1:
			videoTrack = track

		if videoTrack == None:
			raise Exception('No video track found')

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
			errorDecoding(old)
			return

		tmpText = status[old]['text']
		tmpText = string.replace(tmpText, '*', ' ', 1)
		status[old]['text'] = tmpText
		tmpText = status[new]['text']
		tmpText = string.replace(tmpText, ' ', '*', 1)
		status[new]['text'] = tmpText

		if not (new == 8 or new == 0):
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



def errorDecoding(code):
	tkMessageBox.showerror(title='Premature End Of Run', message='The run failed in some way.')

def cleanUp():
	global file

	if os.path.exists(os.path.dirname(file.get()) + os.sep + 'audio.aac'):
		os.remove(os.path.dirname(file.get()) + os.sep + 'audio.aac')

	if os.path.exists(os.path.dirname(file.get()) + os.sep + 'video.h264'):
		os.remove(os.path.dirname(file.get()) + os.sep + 'video.h264')

	if os.path.exists(os.path.dirname(file.get()) + os.sep + 'file.mp4'):
		old = os.path.dirname(file.get()) + os.sep + 'file.mp4'
		new = os.path.splitext(file.get())[0] + '.mp4'
		os.rename(old, new)

def startDecoding():
	global statusQueue

	changeDecodeStatus(0, 1)
	if getMKVInfo() < 0:
		changeDecodeStatus(1, 0)
		changeDecodeStatus(-1, -1)
		cleanUp()
		return

	changeDecodeStatus(1, 2)
	if extractVideo() < 0:
		changeDecodeStatus(2, 0)
		changeDecodeStatus(-2, -2)
		cleanUp()
		return

	changeDecodeStatus(2, 3)
	if correctProfile() < 0:
		changeDecodeStatus(3, 0)
		changeDecodeStatus(-3, -3)
		cleanUp()
		return

	changeDecodeStatus(3, 4)
	if getAudio() < 0:
		changeDecodeStatus(4, 0)
		changeDecodeStatus(-4, -4)
		cleanUp()
		return

	changeDecodeStatus(4, 5)
	if mp4AddVideo() < 0:
		changeDecodeStatus(5, 0)
		changeDecodeStatus(-5, -5)
		cleanUp()
		return

	changeDecodeStatus(5, 6)
	if mp4AddHint() < 0:
		changeDecodeStatus(6, 0)
		changeDecodeStatus(-6, -6)
		cleanUp()
		return

	changeDecodeStatus(6, 7)
	if mp4AddAudioOptimise() < 0:
		changeDecodeStatus(7, 0)
		changeDecodeStatus(-7, -7)
		cleanUp()
		return

	cleanUp()
	changeDecodeStatus(7, 8)

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
	global numPieces, fileSize, sizePerPieceLabel

	numP = numPieces.get()
	sizeP = float(fileSize)/float(numP)

	post = ['KB', 'MB', 'GB', 'TB']

	# so we tweak that to human readable
	tmpSize = float(math.ceil(sizeP))
	for p in post:
		tmpSize = tmpSize/1024.0
		if tmpSize < 1024.0:
			sizePerPieceLabel['text'] = 'Size Per Piece: %0.2f %s'%(tmpSize, p)
			break

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
		piecesMenu['stat'] = DISABLED

def setFileSize():
	global file, fileSize, fileSizeLabel
	post = ['KB', 'MB', 'GB', 'TB']

	# statinfo.st_size in bytes
	statinfo = os.stat(file.get())
	fileSize = statinfo.st_size

	# so we tweak that to human readable
	tmpSize = float(fileSize)
	for p in post:
		tmpSize = tmpSize/1024.0
		if tmpSize < 1024:
			fileSizeLabel['text'] = 'Size: %0.2f %s'%(tmpSize, p)
			break

def setFile():
	global file
	tmp = tkFileDialog.askopenfilename(filetypes=[('Matroska Video Files', '*.mkv')])

	if tmp != "":
		# it won't allow writing otherwise
		file['stat'] = NORMAL
		file.delete(0, END)
		file.insert(INSERT, tmp)
		file['stat'] = DISABLED

		setFileSize()
		checkForLargeFile()
		calcSizePerPiece(-1)

def makeGUI():
	global rootWin, status, file, fileSizeLabel, piecesMenu, numPieces, bitrate, bitrateMenu, goButton, browseButton, sizePerPieceLabel, channels

	# input file portion
	fileEntryFrame = Frame(rootWin)

	Label(fileEntryFrame, text='File: ').pack(side=LEFT)
	file = Entry(fileEntryFrame, width=72, state=DISABLED)
	file.pack(side=LEFT)
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
	piecesMenu['state'] = DISABLED
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
	Label(statusFrame0, text='Status:').pack(side=LEFT, fill=X)
	statusFrame0.pack(side=TOP, fill=X)

	statusFrameA = Frame(statusFrame)
	status.append(Label(statusFrameA, text='* 0: Stopped'))
	statusFrameA.pack(side=TOP, fill=X)

	statusFrameB = Frame(statusFrame)
	status.append(Label(statusFrameB, text='  1: Getting MKV Info'))
	statusFrameB.pack(side=TOP, fill=X)

	statusFrameC = Frame(statusFrame)
	status.append(Label(statusFrameC, text='  2: Extracting Video'))
	statusFrameC.pack(side=TOP, fill=X)

	statusFrameD = Frame(statusFrame)
	status.append(Label(statusFrameD, text='  3: Correcting Profile'))
	statusFrameD.pack(side=TOP, fill=X)

	statusFrameE = Frame(statusFrame)
	status.append(Label(statusFrameE, text='  4: Extracting/Converting Audio'))
	statusFrameE.pack(side=TOP, fill=X)

	statusFrameF = Frame(statusFrame)
	status.append(Label(statusFrameF, text='  5: Adding Video To MP4'))
	statusFrameF.pack(side=TOP, fill=X)

	statusFrameG = Frame(statusFrame)
	status.append(Label(statusFrameG, text='  6: Hinting Video'))
	statusFrameG.pack(side=TOP, fill=X)

	statusFrameH = Frame(statusFrame)
	status.append(Label(statusFrameH, text='  7: Adding Audio And Optimising MP4'))
	statusFrameH.pack(side=TOP, fill=X)

	statusFrameI = Frame(statusFrame)
	status.append(Label(statusFrameI, text='  8: Done'))
	statusFrameI.pack(side=TOP, fill=X)

	for i in status:
		i.pack(side=LEFT, fill=X)

	statusFrame.pack(side=TOP, fill=X)


	# go button
	goFrame = Frame(rootWin)
	goButton = Button(goFrame, text='Start', command=decode)
	goButton.pack(side=BOTTOM)
	goFrame.pack(side=BOTTOM, fill=X)



if __name__ == '__main__':
	global rootWin, statusQueue

	statusQueue = Queue.Queue()

	rootWin = Tk()
	rootWin.title("MKV2PS3MP4")
	makeGUI()
	rootWin.mainloop()

