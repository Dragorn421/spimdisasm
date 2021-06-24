#!/usr/bin/python3

from __future__ import annotations

from .Utils import *
from .GlobalConfig import GlobalConfig

from .MipsText import Text
from .MipsData import Data
from .MipsRodata import Rodata
from .MipsBss import Bss
from .MipsFileGeneric import FileGeneric
from .MipsContext import Context

from .ZeldaOffsets import bootVramStart, bootDataStart, bootRodataStart


class FileBoot(FileGeneric):
    def __init__(self, array_of_bytes: bytearray, filename: str, version: str, context: Context):
        super().__init__(array_of_bytes, filename, version, context)

        self.vRamStart = bootVramStart[version]

        text_start = 0
        data_start = bootDataStart[version]
        rodata_start = bootRodataStart[version]
        # bss_start = bootBssStart[version]
        bss_start = self.size

        self.text = Text(self.bytes[text_start:data_start], filename, version, context)
        self.text.parent = self
        self.text.offset = text_start
        self.text.vRamStart = self.vRamStart

        self.data = Data(self.bytes[data_start:rodata_start], filename, version, context)
        self.data.parent = self
        self.data.offset = data_start
        self.data.vRamStart = self.vRamStart

        self.rodata = Rodata(self.bytes[rodata_start:bss_start], filename, version, context)
        self.rodata.parent = self
        self.rodata.offset = rodata_start
        self.rodata.vRamStart = self.vRamStart

        self.bss = Bss(self.bytes[bss_start:self.size], filename, version, context)
        self.bss.parent = self
        self.bss.offset = bss_start
        self.bss.vRamStart = self.vRamStart

        self.text.removeTrailingNops()
        self.text.findFunctions()
