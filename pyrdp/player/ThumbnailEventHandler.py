#
# This file is part of the PyRDP project.
# Copyright (C) 2020-2021 GoSecure Inc.
# Licensed under the GPLv3 or later.
#

from pyrdp.enum import BitmapFlags, CapabilityType
from pyrdp.pdu import BitmapUpdateData, PlayerPDU
from pyrdp.player.RenderingEventHandler import RenderingEventHandler
from pyrdp.ui import RDPBitmapToQtImage

import logging

import av
from PIL import ImageQt
from PySide2.QtGui import QImage, QPainter, QColor
from os import path

from pyrdp.player.Mp4EventHandler import Mp4Sink


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

        if args.output:
            self.dst = args.output

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
        # Draw the mouse pointer. Render mouse clicks?
        if self.timestamp - self.prevTimestamp < self.delta:
            return

        tmp = surface.copy()
        p = QPainter(tmp)
        p.setBrush(QColor.fromRgb(255, 255, 0, 180))
        (x, y) = self.mouse
        p.drawEllipse(x, y, 5, 5)
        p.end()
        self.prevTimestamp = self.timestamp
        tmp.save(path.join(self.dst, f'{self.timestamp}.png'))
        del tmp



