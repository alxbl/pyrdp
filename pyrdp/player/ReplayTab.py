#
# This file is part of the PyRDP project.
# Copyright (C) 2019-2021 GoSecure Inc.
# Licensed under the GPLv3 or later.
#
import os
import pickle
from typing import Dict, Optional

from PySide2.QtCore import QByteArray
from PySide2.QtGui import QImage, QResizeEvent
from PySide2.QtWidgets import QApplication, QWidget

from pyrdp.player.BaseTab import BaseTab
from pyrdp.player.gdi.cache import BitmapCache
from pyrdp.player.gdi.SerializableBitmapCache import SerializableBitmapCache
from pyrdp.player.PlayerEventHandler import PlayerEventHandler
from pyrdp.player.Replay import Replay, ReplayReader
from pyrdp.player.ReplayBar import ReplayBar
from pyrdp.player.ReplayThread import ReplayThread
from pyrdp.ui import QRemoteDesktop


class ReplayTab(BaseTab):
    """
    Tab that displays a RDP Connection that is being replayed from a file.
    """

    def __init__(self, fileName: str, parent: QWidget, thumbnail_directory: Optional[str] = None):
        """
        :param fileName: name of the file to read.
        :param parent: parent widget.
        """
        self.viewer = QRemoteDesktop(800, 600, parent)

        super().__init__(self.viewer, parent)
        QApplication.instance().aboutToQuit.connect(self.onClose)

        self.fileName = fileName
        self.file = open(self.fileName, "rb")
        self.eventHandler = PlayerEventHandler(self.widget, self.text)

        thumbnails = self.makeThumbnailsMap(thumbnail_directory)

        replay = Replay(self.file)
        self.reader = ReplayReader(replay)
        self.thread = ReplayThread(replay, thumbnails=thumbnails if thumbnail_directory else None)
        self.thread.eventReached.connect(self.readEvent)
        self.thread.timeUpdated.connect(self.onTimeUpdated)
        self.thread.clearNeeded.connect(self.clear)
        self.thread.paintThumbnail.connect(self.paintThumbnail)
        self.thread.start()

        self.controlBar = ReplayBar(replay.duration)
        self.controlBar.play.connect(self.thread.play)
        self.controlBar.pause.connect(self.thread.pause)
        self.controlBar.seek.connect(self.thread.seek)
        self.controlBar.speedChanged.connect(self.thread.setSpeed)
        self.controlBar.scaleCheckbox.stateChanged.connect(self.setScaleToWindow)
        self.controlBar.button.setDefault(True)

        self.tabLayout.insertWidget(0, self.controlBar)

    def makeThumbnailsMap(self, thumbnail_directory):
        thumbnails = {}
        first_thumbnail_timestamp = 0
        if thumbnail_directory:
            for i, file in enumerate(os.listdir(thumbnail_directory)):
                if file.endswith(".png"):
                    timestamp = int(file.replace('.png', ''))
                    if i == 0:
                        first_thumbnail_timestamp = timestamp
                    thumbnails[timestamp - first_thumbnail_timestamp] = (
                    f"{thumbnail_directory}/{file}",
                    f"{thumbnail_directory}/gdi_cache/{file}".replace('.png', '.bitmapcache'))
        return thumbnails

    def play(self):
        self.controlBar.button.setPlaying(True)
        self.controlBar.play.emit()

    def readEvent(self, position: int):
        """
        Read an event from the file at the given position.
        :param position: the position of the event in the file.
        """
        event = self.reader.readEvent(position)
        self.eventHandler.onPDUReceived(event)

    def onTimeUpdated(self, currentTime: float):
        """
        Called everytime the thread ticks.
        :param currentTime: the current time.
        """
        self.controlBar.timeSlider.blockSignals(True)
        self.controlBar.timeSlider.setValue(int(currentTime * 1000))
        self.controlBar.timeSlider.blockSignals(False)

    def clear(self):
        """
        Clear the UI.
        """
        self.viewer.clear()
        self.text.setText("")

    def paintThumbnail(self, thumbnailFilePath: str, bitmapCachePath: str):
        with open(thumbnailFilePath, 'rb') as file:
            png_content = file.read()

        qimage = QImage()
        qimage.loadFromData(QByteArray(png_content))
        self.viewer.notifyImage(0, 0, qimage, qimage.width(), qimage.height())

        # We also need to deserialize the bitmap cache.
        print(f"load {bitmapCachePath}")
        with open(bitmapCachePath, 'rb') as file:
            serializableBitmapCaches: Dict[int, SerializableBitmapCache] = pickle.load(file)

        bitmapCache = BitmapCache()
        for key, serializableCache in serializableBitmapCaches.items():
            bitmapCache.caches[key] = serializableCache.cache

        self.eventHandler.gdi.bitmaps = bitmapCache

    def onClose(self):
        self.thread.close()
        self.thread.wait()
        self.eventHandler.cleanup()

    def setScaleToWindow(self, status: int):
        """
        Called when the scale to window checkbox is checked or unchecked, refresh
        the scaling calculation.
        :param status: state of the checkbox
        """
        self.widget.setScaleToWindow(status)
        self.parentResized(None)

    def parentResized(self, event: QResizeEvent):
        """
        Called when the main PyRDP window is resized to allow to scale the current
        RDP session being displayed.
        :param event: The event of the parent that has been resized
        """
        newScale = self.scrollViewer.viewport().height() / self.widget.sessionHeight
        self.widget.scale(newScale)
