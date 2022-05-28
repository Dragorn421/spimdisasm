#!/usr/bin/env python3

# SPDX-FileCopyrightText: © 2022 Decompollaborate
# SPDX-License-Identifier: MIT

from __future__ import annotations

from ... import common

from . import SymbolBase


class SymbolData(SymbolBase):
    def __init__(self, context: common.Context, vromStart: int, vromEnd: int, inFileOffset: int, vram: int, words: list[int], segmentVromStart: int, overlayType: str|None):
        super().__init__(context, vromStart, vromEnd, inFileOffset, vram, words, common.FileSectionType.Data, segmentVromStart, overlayType)
