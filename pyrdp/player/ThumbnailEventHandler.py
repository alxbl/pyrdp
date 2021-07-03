#
# This file is part of the PyRDP project.
# Copyright (C) 2020-2021 GoSecure Inc.
# Licensed under the GPLv3 or later.
#
import logging
import os
import pickle
from os import path
from pathlib import Path

from PySide2.QtGui import QColor, QImage, QPainter

from pyrdp.enum import CapabilityType
from pyrdp.pdu import PlayerPDU
from pyrdp.player.gdi.SerializableBitmapCache import SerializableBitmapCache
from pyrdp.player.Mp4EventHandler import Mp4Sink
from pyrdp.player.RenderingEventHandler import RenderingEventHandler

DEFAULT_DELTA = 300  # seconds


class ThumbnailEventHandler(RenderingEventHandler):

    def __init__(self, dstDir: str, progress=None):
        """
        Construct an event handler that outputs a thumbnail stream.

        :param dstDir: The output directory to write thumbnails to.
        :param progress: An optional callback (sig: `() -> ()`) whenever a thumbnail is written.
        """

        self.sink = Mp4Sink()
        self.dst = dstDir
        self.progress = progress
        self.mouse = (0, 0)
        self.delta = DEFAULT_DELTA
        self.log = logging.getLogger(__name__)
        self.timestamp = self.prevTimestamp = 0

        super().__init__(self.sink)

    def onPDUReceived(self, pdu: PlayerPDU):
        super().onPDUReceived(pdu)

        # Make sure the rendering surface has been created.
        if self.sink.screen is None:
            return

        self.timestamp = pdu.timestamp
        self._writeFrame(self.sink.screen)

    def configure(self, args):
        # Timestamps are in milliseconds.
        self.delta = (args.thumbnails if args.thumbnails else DEFAULT_DELTA) * 1000

        self.start = args.start if args.start else None
        self.stop = args.stop if args.stop else None

        if args.output:
            self.dst = args.output

        outDir = Path(self.dst)
        outDir.mkdir(exist_ok=True)

    def onMousePosition(self, x, y):
        self.mouse = (x, y)
        super().onMousePosition(x, y)

    def onCapabilities(self, caps):
        bmp = caps[CapabilityType.CAPSTYPE_BITMAP]
        (w, h) = (bmp.desktopWidth, bmp.desktopHeight)
        self.sink.resize(w, h)
        super().onCapabilities(caps)

    def onFinishRender(self):
        self._writeFrame(self.sink.screen)

    def _writeFrame(self, surface: QImage):
        # We need to play from the beginning to get the full image.
        # just ignore the delta for frames before the start time.
        if self.start and self.timestamp < self.start:
            return

        if self.stop and self.timestamp > self.stop:
            # We could technically exit here, but this is easier for now.
            # This code will need to be refactored if we ever bring it into
            # the main branch.
            return

        if self.timestamp - self.prevTimestamp < self.delta:
            return

        tmp = surface.copy()  # create a copy of the frame to paint the cursor.
        p = QPainter(tmp)
        p.setBrush(QColor.fromRgb(255, 255, 0, 180))
        (x, y) = self.mouse
        p.drawEllipse(x, y, 5, 5)
        p.end()
        self.prevTimestamp = self.timestamp
        tmp.save(path.join(self.dst, f'{self.timestamp}.png'))
        del tmp

        self.save_bitmap_cache()

    def save_bitmap_cache(self):
        gdi_cache_directory = path.join(self.dst, 'gdi_cache')
        serializable_bitmaps = {}
        for key, bitmap in self.gdi.bitmaps.caches.items():
            serializable_bitmaps[key] = SerializableBitmapCache(bitmap)
        if not os.path.exists(gdi_cache_directory):
            os.makedirs(gdi_cache_directory, exist_ok=True)
        bitmapCachePath = path.join(gdi_cache_directory, f'{self.timestamp}.bitmapcache')
        with open(bitmapCachePath, "wb") as file:
            pickle.dump(serializable_bitmaps, file)
            del serializable_bitmaps
