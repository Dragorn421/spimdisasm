#!/usr/bin/env python3

# SPDX-FileCopyrightText: © 2022 Decompollaborate
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from typing import TextIO

from .. import common

from . import symbols


class FileBase(common.ElementBase):
    def __init__(self, context: common.Context, vromStart: int, vromEnd: int, vram: int, filename: str, array_of_bytes: bytearray, sectionType: common.FileSectionType):
        super().__init__(context, vromStart, vromEnd, 0, vram, filename, common.Utils.bytesToBEWords(array_of_bytes), sectionType)

        self.symbolList: list[symbols.SymbolBase] = []

        self.pointersOffsets: set[int] = set()

        self.isHandwritten: bool = False
        self.isRsp: bool = False


    def setCommentOffset(self, commentOffset: int):
        self.commentOffset = commentOffset
        for sym in self.symbolList:
            sym.setCommentOffset(self.commentOffset)

    def getAsmPrelude(self) -> str:
        output = ""

        output += ".include \"macro.inc\"" + common.GlobalConfig.LINE_ENDS
        output += common.GlobalConfig.LINE_ENDS
        output += "# assembler directives" + common.GlobalConfig.LINE_ENDS
        output += ".set noat      # allow manual use of $at" + common.GlobalConfig.LINE_ENDS
        output += ".set noreorder # don't insert nops after branches" + common.GlobalConfig.LINE_ENDS
        output += ".set gp=64     # allow use of 64-bit general purpose registers" + common.GlobalConfig.LINE_ENDS
        output += common.GlobalConfig.LINE_ENDS
        output += f".section {self.sectionType.toSectionName()}" + common.GlobalConfig.LINE_ENDS
        output += common.GlobalConfig.LINE_ENDS
        output += ".balign 16" + common.GlobalConfig.LINE_ENDS

        return output

    def getHash(self) -> str:
        buffer = bytearray(4*len(self.words))
        common.Utils.beWordsToBytes(self.words, buffer)
        return common.Utils.getStrHash(buffer)


    def checkAndCreateFirstSymbol(self) -> None:
        "Check if the very start of the file has a symbol and create it if it doesn't exist yet"

        if not common.GlobalConfig.ADD_NEW_SYMBOLS:
            return

        currentVram = self.getVramOffset(0)
        contextSym = self.context.getSymbol(currentVram, False)
        if contextSym is None:
            contextSym = self.context.addSymbol(currentVram, self.sectionType, isAutogenerated=True)
            contextSym.isDefined = True


    def printAnalyzisResults(self):
        pass

    def compareToFile(self, other_file: FileBase) -> dict:
        hash_one = self.getHash()
        hash_two = other_file.getHash()

        result = {
            "equal": hash_one == hash_two,
            "hash_one": hash_one,
            "hash_two": hash_two,
            "size_one": self.sizew * 4,
            "size_two": other_file.sizew * 4,
            "diff_bytes": 0,
            "diff_words": 0,
        }

        diff_bytes = 0
        diff_words = 0

        if not result["equal"]:
            min_len = min(self.sizew, other_file.sizew)
            for i in range(min_len):
                for j in range(4):
                    if (self.words[i] & (0xFF << (j * 8))) != (other_file.words[i] & (0xFF << (j * 8))):
                        diff_bytes += 1

            min_len = min(self.sizew, other_file.sizew)
            for i in range(min_len):
                if self.words[i] != other_file.words[i]:
                    diff_words += 1

        result["diff_bytes"] = diff_bytes
        result["diff_words"] = diff_words

        return result

    def blankOutDifferences(self, other: FileBase) -> bool:
        if not common.GlobalConfig.REMOVE_POINTERS:
            return False

        return False

    def removePointers(self) -> bool:
        if not common.GlobalConfig.REMOVE_POINTERS:
            return False

        return False


    def disassemble(self) -> str:
        output = ""
        for i, sym in enumerate(self.symbolList):
            output += sym.disassemble()
            if i + 1 < len(self.symbolList):
                output += common.GlobalConfig.LINE_ENDS
        return output

    def disassembleToFile(self, f: TextIO):
        f.write(self.getAsmPrelude())
        f.write(common.GlobalConfig.LINE_ENDS)
        f.write(self.disassemble())


    def saveToFile(self, filepath: str):
        if len(self.symbolList) == 0:
            return

        if filepath == "-":
            self.disassembleToFile(sys.stdout)
        else:
            if common.GlobalConfig.WRITE_BINARY:
                if self.sizew > 0:
                    buffer = bytearray(4*len(self.words))
                    common.Utils.beWordsToBytes(self.words, buffer)
                    common.Utils.writeBytearrayToFile(filepath + self.sectionType.toStr(), buffer)
            with open(filepath + self.sectionType.toStr() + ".s", "w") as f:
                self.disassembleToFile(f)


def createEmptyFile() -> FileBase:
    return FileBase(common.Context(), 0, 0, 0, "", bytearray(), common.FileSectionType.Unknown)
