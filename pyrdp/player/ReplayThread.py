#
# This file is part of the PyRDP project.
# Copyright (C) 2018-2021 GoSecure Inc.
# Licensed under the GPLv3 or later.
#

import queue
from enum import IntEnum
from multiprocessing import Queue
from time import sleep
from typing import Dict, Optional, Tuple

from PySide2.QtCore import QThread, Signal

from pyrdp.core import Timer
from pyrdp.player.Replay import Replay


class ReplayThreadEvent(IntEnum):
    """
    Types of messages that can be sent to the replay thread.
    """
    PLAY = 0
    PAUSE = 1
    SEEK = 2
    SPEED = 3
    EXIT = 4


class ReplayThread(QThread):
    """
    Thread that runs in the background for every replay. Constantly checks time to see which events should be played.
    """

    timeUpdated = Signal(float)

    # We use the object type instead of int for this signal to prevent Python integers from being converted to 32-bit integers
    eventReached = Signal(object)
    clearNeeded = Signal()
    paintThumbnail = Signal(str, str)

    def __init__(self, replay: Replay, thumbnails: Optional[Dict[int, Tuple[str, str]]] = None):
        super().__init__()

        self.thumbnails = thumbnails
        self.queue = Queue()
        self.lastSeekTime = 0
        self.requestedSpeed = 1
        self.replay = replay
        self.timer = Timer()
        self.thumbnail_timestamp = 0

    def run(self):
        step = 16 / 1000
        currentIndex = 0
        runThread = True
        timestamps = self.replay.getSortedTimestamps()

        while runThread:
            self.timer.update()

            try:
                while True:
                    event = self.queue.get_nowait()

                    if event == ReplayThreadEvent.PLAY:
                        self.timer.start()
                    elif event == ReplayThreadEvent.PAUSE:
                        self.timer.stop()
                    elif event == ReplayThreadEvent.SEEK:
                        if self.thumbnails:
                            self.thumbnail_timestamp = self.get_thumbnail_timestamp(self.lastSeekTime)
                            self.paintThumbnail.emit(self.thumbnails[self.thumbnail_timestamp][0],
                                                     self.thumbnails[self.thumbnail_timestamp][1])
                            currentIndex = 0
                        elif self.lastSeekTime < self.timer.getElapsedTime():
                            currentIndex = 0
                            self.clearNeeded.emit()

                        self.timer.setTime(self.lastSeekTime)
                    elif event == ReplayThreadEvent.SPEED:
                        self.timer.setSpeed(self.requestedSpeed)
                    elif event == ReplayThreadEvent.EXIT:
                        runThread = False

            except queue.Empty:
                pass

            if self.timer.isRunning():
                currentTime = self.timer.getElapsedTime()
                self.timeUpdated.emit(currentTime)

                while currentIndex < len(timestamps) and timestamps[currentIndex] / 1000.0 <= currentTime:
                    nextTimestamp = timestamps[currentIndex]

                    # Only replay an event if it's after the latest thumbnail printed.
                    if not self.thumbnails or nextTimestamp >= self.thumbnail_timestamp:
                        positions = self.replay.events[nextTimestamp]

                        for position in positions:
                            self.eventReached.emit(position)

                    currentIndex += 1

            sleep(step)

    def get_thumbnail_timestamp(self, seek_time: int):
        best_thumbnail = -1
        for thumbnail_timestamp in self.thumbnails.keys():
            if best_thumbnail < thumbnail_timestamp < seek_time * 1000:
                best_thumbnail = thumbnail_timestamp
        return best_thumbnail

    def play(self):
        self.queue.put(ReplayThreadEvent.PLAY)

    def pause(self):
        self.queue.put(ReplayThreadEvent.PAUSE)

    def seek(self, time: float):
        self.lastSeekTime = time
        self.queue.put(ReplayThreadEvent.SEEK)

    def setSpeed(self, speed: float):
        self.requestedSpeed = speed
        self.queue.put(ReplayThreadEvent.SPEED)

    def close(self):
        self.queue.put(ReplayThreadEvent.EXIT)
