#!/usr/bin/env python3

# SPDX-FileCopyrightText: © 2022 Decompollaborate
# SPDX-License-Identifier: MIT

from __future__ import annotations

import rabbitizer

from ... import common

from .. import symbols

from . import SectionBase


class SectionRodata(SectionBase):
    def __init__(self, context: common.Context, vromStart: int, vromEnd: int, vram: int, filename: str, array_of_bytes: bytes, segmentVromStart: int, overlayCategory: str|None):
        if common.GlobalConfig.ENDIAN_RODATA is not None:
            words = common.Utils.endianessBytesToWords(common.GlobalConfig.ENDIAN_RODATA, array_of_bytes, vromStart, vromEnd)
        else:
            words = common.Utils.bytesToWords(array_of_bytes, vromStart, vromEnd)
        super().__init__(context, vromStart, vromEnd, vram, filename, words, common.FileSectionType.Rodata, segmentVromStart, overlayCategory)

        self.stringEncoding = "EUC-JP"


    def analyze(self):
        self.checkAndCreateFirstSymbol()

        symbolList = []
        localOffset = 0

        lastVramSymbol: common.ContextSymbol | None = None

        partOfJumpTable = False
        firstJumptableWord = -1

        for w in self.words:
            currentVram = self.getVramOffset(localOffset)
            currentVrom = self.getVromOffset(localOffset)
            contextSym = self.getSymbol(currentVram, vromAddress=currentVrom, tryPlusOffset=False)

            if contextSym is not None:
                lastVramSymbol = contextSym


            if contextSym is not None and contextSym.isJumpTable():
                partOfJumpTable = True
                firstJumptableWord = w

            elif partOfJumpTable:
                # The last symbol found was part of a jumptable, check if this word still is part of the jumptable

                if localOffset in self.pointersOffsets:
                    partOfJumpTable = True

                elif w == 0:
                    partOfJumpTable = False

                elif contextSym is not None:
                    partOfJumpTable = False

                elif ((w >> 24) & 0xFF) != ((firstJumptableWord >> 24) & 0xFF):
                    partOfJumpTable = False
                    if lastVramSymbol is not None and lastVramSymbol.isJumpTable() and lastVramSymbol.isGot and common.GlobalConfig.GP_VALUE is not None:
                        partOfJumpTable = True


            if partOfJumpTable:
                if lastVramSymbol is not None and lastVramSymbol.isGot and common.GlobalConfig.GP_VALUE is not None:
                    labelAddr = common.GlobalConfig.GP_VALUE + rabbitizer.Utils.from2Complement(w, 32)
                    labelSym = self.addJumpTableLabel(labelAddr, isAutogenerated=True)
                else:
                    labelSym = self.addJumpTableLabel(w, isAutogenerated=True)
                if labelSym.unknownSegment:
                    partOfJumpTable = False
                else:
                    labelSym.referenceCounter += 1

            if not partOfJumpTable:
                if self.popPointerInDataReference(currentVram) is not None:
                    contextSym = self.addSymbol(currentVram, sectionType=self.sectionType, isAutogenerated=True)
                    contextSym.isMaybeString = self._stringGuesser(contextSym, localOffset)
                    contextSym.isMaybePascalString = self._pascalStringGuesser(contextSym, localOffset)
                    lastVramSymbol = contextSym

                elif contextSym is not None:
                    contextSym.isMaybeString = self._stringGuesser(contextSym, localOffset)
                    contextSym.isMaybePascalString = self._pascalStringGuesser(contextSym, localOffset)

                elif lastVramSymbol is not None and lastVramSymbol.isJumpTable() and w != 0:
                    contextSym = self.addSymbol(currentVram, sectionType=self.sectionType, isAutogenerated=True)
                    contextSym.isMaybeString = self._stringGuesser(contextSym, localOffset)
                    contextSym.isMaybePascalString = self._pascalStringGuesser(contextSym, localOffset)
                    lastVramSymbol = contextSym

                self.checkWordIsASymbolReference(w)

            if contextSym is not None:
                self.symbolsVRams.add(currentVram)
                symbolList.append((localOffset, currentVram))

                if common.GlobalConfig.CREATE_RODATA_PADS and contextSym.hasUserDeclaredSize():
                    symDeclaredSize = contextSym.getSize()
                    if symDeclaredSize > 0 and localOffset + symDeclaredSize < self.sizew * 4:
                        # Try to respect the user-declared size for this symbol
                        extraContextSym = self.addSymbol(contextSym.vram+symDeclaredSize, sectionType=self.sectionType, isAutogenerated=True, symbolVrom=currentVrom+symDeclaredSize)
                        extraContextSym.isAutoCreatedPad = True

            localOffset += 4

        previousSymbolWasLateRodata = False
        previousSymbolExtraPadding = 0

        for i, (offset, vram) in enumerate(symbolList):
            if i + 1 == len(symbolList):
                words = self.words[offset//4:]
            else:
                nextOffset = symbolList[i+1][0]
                words = self.words[offset//4:nextOffset//4]

            vrom = self.getVromOffset(offset)
            vromEnd = vrom + len(words)*4
            sym = symbols.SymbolRodata(self.context, vrom, vromEnd, offset + self.inFileOffset, vram, words, self.segmentVromStart, self.overlayCategory)
            sym.parent = self
            sym.setCommentOffset(self.commentOffset)
            sym.stringEncoding = self.stringEncoding
            sym.analyze()
            self.symbolList.append(sym)

            # File boundaries detection
            if sym.inFileOffset % 16 == 0:
                # Files are always 0x10 aligned

                if previousSymbolWasLateRodata and not sym.contextSym.isLateRodata():
                    # late rodata followed by normal rodata implies a file split
                    self.fileBoundaries.append(sym.inFileOffset)
                elif previousSymbolExtraPadding > 0:
                    if sym.isDouble(0):
                        # doubles require a bit extra of alignment
                        if previousSymbolExtraPadding >= 2:
                            self.fileBoundaries.append(sym.inFileOffset)
                    elif sym.isJumpTable() and common.GlobalConfig.COMPILER != common.Compiler.IDO:
                        # non-IDO compilers emit a directive to align jumptables to 0x8 boundary
                        if previousSymbolExtraPadding >= 2:
                            self.fileBoundaries.append(sym.inFileOffset)
                    else:
                        self.fileBoundaries.append(sym.inFileOffset)

            previousSymbolWasLateRodata = sym.contextSym.isLateRodata()
            previousSymbolExtraPadding = sym.countExtraPadding()

        self.processStaticRelocs()

        # Filter out repeated values and sort
        self.fileBoundaries = sorted(set(self.fileBoundaries))


    def removePointers(self) -> bool:
        if not common.GlobalConfig.REMOVE_POINTERS:
            return False

        was_updated = super().removePointers()
        for i in range(self.sizew):
            top_byte = (self.words[i] >> 24) & 0xFF
            if top_byte == 0x80:
                self.words[i] = top_byte << 24
                was_updated = True
            if (top_byte & 0xF0) == 0x00 and (top_byte & 0x0F) != 0x00:
                self.words[i] = top_byte << 24
                was_updated = True

        return was_updated
