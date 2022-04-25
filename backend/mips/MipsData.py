#!/usr/bin/env python3

from __future__ import annotations

from ..common.Utils import *
from ..common.GlobalConfig import GlobalConfig
from ..common.Context import Context
from ..common.FileSectionType import FileSectionType

from .MipsSection import Section
from .Symbols import SymbolData


class Data(Section):
    def __init__(self, array_of_bytes: bytearray, filename: str, context: Context):
        super().__init__(array_of_bytes, filename, context)

        self.symbolList: list[SymbolData] = []

    def analyze(self):
        symbolList = []

        localOffset = 0
        currentVram = self.getVramOffset(localOffset)

        # Make sure the start of the data section is a symbol
        contextSym = self.context.getSymbol(currentVram, tryPlusOffset=False)
        if contextSym is None:
            contextSym = self.context.addSymbol(currentVram, None)
            contextSym.isAutogenerated = True
        contextSym.isDefined = True
        symbolList.append((contextSym.name, localOffset, currentVram))

        for w in self.words:
            currentVram = self.getVramOffset(localOffset)

            contextSym = self.context.getSymbol(currentVram, tryPlusOffset=False)
            if contextSym is not None:
                contextSym.isDefined = True
                if localOffset != 0:
                    symbolList.append((contextSym.name, localOffset, currentVram))

            if self.vRamStart > -1:
                if w >= self.vRamStart and w < 0x84000000:
                    if self.context.getAnySymbol(w) is None:
                        self.context.newPointersInData.add(w)

            localOffset += 4

        for i, (symName, offset, vram) in enumerate(symbolList):
            if i + 1 == len(symbolList):
                words = self.words[offset//4:]
            else:
                words = self.words[offset//4:symbolList[i+1][1]//4]

            symVram = None
            if self.vRamStart > -1:
                symVram = vram

            sym = SymbolData(self.context, symName, offset + self.inFileOffset, symVram, words)
            sym.setCommentOffset(self.commentOffset)
            sym.analyze()
            self.symbolList.append(sym)


    def removePointers(self) -> bool:
        if not GlobalConfig.REMOVE_POINTERS:
            return False

        was_updated = False
        for i in range(self.sizew):
            top_byte = (self.words[i] >> 24) & 0xFF
            if top_byte == 0x80:
                self.words[i] = top_byte << 24
                was_updated = True
            if (top_byte & 0xF0) == 0x00 and (top_byte & 0x0F) != 0x00:
                self.words[i] = top_byte << 24
                was_updated = True

        return was_updated


    def disassembleToFile(self, f: TextIO):
        f.write(".include \"macro.inc\"\n")
        f.write("\n")
        f.write("# assembler directives\n")
        f.write(".set noat      # allow manual use of $at\n")
        f.write(".set noreorder # don't insert nops after branches\n")
        f.write(".set gp=64     # allow use of 64-bit general purpose registers\n")
        f.write("\n")
        f.write(".section .data\n")
        f.write("\n")
        f.write(".balign 16\n")

        for sym in self.symbolList:
            f.write(sym.disassemble())

    def saveToFile(self, filepath: str):
        super().saveToFile(filepath + ".data")

        if self.size == 0:
            return

        if filepath == "-":
            self.disassembleToFile(sys.stdout)
        else:
            with open(filepath + ".data.s", "w") as f:
                self.disassembleToFile(f)
