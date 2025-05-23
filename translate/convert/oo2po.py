#
# Copyright 2003-2008 Zuza Software Foundation
#
# This file is part of translate.
#
# translate is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# translate is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.
#

"""
Convert an OpenOffice.org (SDF) localization file to Gettext PO localization files.

See: http://docs.translatehouse.org/projects/translate-toolkit/en/latest/commands/oo2po.html
for examples and usage instructions.
"""

import logging
from urllib import parse

from translate.storage import oo, po

# TODO: support using one GSI file as template, another as input (for when English is in one and translation in another)

logger = logging.getLogger(__name__)


class oo2po:
    def __init__(
        self, sourcelanguage, targetlanguage, blankmsgstr=False, long_keys=False
    ):
        """Construct an oo2po converter for the specified languages."""
        self.sourcelanguage = sourcelanguage
        self.targetlanguage = targetlanguage
        self.blankmsgstr = blankmsgstr
        self.long_keys = long_keys

    @staticmethod
    def maketargetunit(part1, part2, translators_comment, key, subkey):
        """Makes a base unit (.po or XLIFF) out of a subkey of two parts."""
        # TODO: Do better
        text1 = getattr(part1, subkey)
        if not text1:
            return None
        text2 = getattr(part2, subkey)

        unit = po.pounit(text1, encoding="UTF-8")
        unit.target = text2
        unit.addlocation(key + "." + subkey)
        if getattr(translators_comment, subkey).strip():
            unit.addnote(getattr(translators_comment, subkey), origin="developer")
        return unit

    def convertelement(self, theoo):
        """Convert an oo element into a list of base units (.po or XLIFF)."""
        if self.sourcelanguage in theoo.languages:
            part1 = theoo.languages[self.sourcelanguage]
        else:
            logger.error(
                "%s language not found: %s",
                "/".join(theoo.lines[0].getkey()),
                self.sourcelanguage,
            )
            return []
        if self.blankmsgstr:
            # use a blank part2
            part2 = oo.ooline()
        elif self.targetlanguage in theoo.languages:
            part2 = theoo.languages[self.targetlanguage]
        else:
            # if the language doesn't exist, the translation is missing ... so make it blank
            part2 = oo.ooline()
        if "x-comment" in theoo.languages:
            translators_comment = theoo.languages["x-comment"]
        else:
            translators_comment = oo.ooline()
        key = oo.makekey(part1.getkey(), self.long_keys)
        unitlist = []
        for subkey in ("text", "quickhelptext", "title"):
            unit = self.maketargetunit(part1, part2, translators_comment, key, subkey)
            if unit is not None:
                unitlist.append(unit)
        return unitlist

    def convertstore(self, theoofile, duplicatestyle="msgctxt"):
        """Converts an entire oo file to a base class format (.po or XLIFF)."""
        thetargetfile = po.pofile()
        # create a header for the file
        bug_url = "http://qa.openoffice.org/issues/enter_bug.cgi?{}".format(
            parse.urlencode(
                {
                    "subcomponent": "ui",
                    "comment": "",
                    "short_desc": f"Localization issue in file: {theoofile.filename}",
                    "component": "l10n",
                    "form_name": "enter_issue",
                }
            )
        )
        targetheader = thetargetfile.init_headers(
            x_accelerator_marker="~",
            x_merge_on="location",
            report_msgid_bugs_to=bug_url,
        )
        targetheader.addnote(f"extracted from {theoofile.filename}", "developer")
        thetargetfile.setsourcelanguage(self.sourcelanguage)
        thetargetfile.settargetlanguage(self.targetlanguage)
        # go through the oo and convert each element
        for theoo in theoofile.units:
            unitlist = self.convertelement(theoo)
            for unit in unitlist:
                thetargetfile.addunit(unit)
        thetargetfile.removeduplicates(duplicatestyle)
        return thetargetfile


def verifyoptions(options):
    """Verifies the commandline options."""
    if not options.pot and not options.targetlanguage:
        raise ValueError(
            "You must specify the target language unless generating POT files (-P)"
        )


def convertoo(
    inputfile,
    outputfile,
    templates,
    pot=False,
    sourcelanguage=None,
    targetlanguage=None,
    duplicatestyle="msgid_comment",
    multifilestyle="single",
):
    """Reads in stdin using inputstore class, converts using convertorclass, writes to stdout."""
    inputstore = oo.oofile()
    if hasattr(inputfile, "filename"):
        inputfilename = inputfile.filename
    else:
        inputfilename = "(input file name not known)"
    inputstore.filename = inputfilename
    inputstore.parse(inputfile.read())
    if not sourcelanguage:
        testlangtype = targetlanguage or (inputstore and inputstore.languages[0]) or ""
        sourcelanguage = "01" if testlangtype.isdigit() else "en-US"
    if sourcelanguage not in inputstore.languages:
        logger.warning(
            "sourcelanguage '%s' not found in inputfile '%s' (contains %s)",
            sourcelanguage,
            inputfilename,
            ", ".join(inputstore.languages),
        )
    if targetlanguage and targetlanguage not in inputstore.languages:
        logger.warning(
            "targetlanguage '%s' not found in inputfile '%s' (contains %s)",
            targetlanguage,
            inputfilename,
            ", ".join(inputstore.languages),
        )
    convertor = oo2po(
        sourcelanguage,
        targetlanguage,
        blankmsgstr=pot,
        long_keys=multifilestyle != "single",
    )
    outputstore = convertor.convertstore(inputstore, duplicatestyle)
    if outputstore.isempty():
        return 0
    outputstore.serialize(outputfile)
    return 1


def main(argv=None):
    from translate.convert import convert

    formats = {
        "oo": ("po", convertoo),
        "sdf": ("po", convertoo),
    }
    # always treat the input as an archive unless it is a directory
    archiveformats = {(None, "input"): oo.oomultifile}
    parser = convert.ArchiveConvertOptionParser(
        formats, usepots=True, description=__doc__, archiveformats=archiveformats
    )
    parser.add_option(
        "-l",
        "--language",
        dest="targetlanguage",
        default=None,
        help="set target language to extract from oo file (e.g. af-ZA)",
        metavar="LANG",
    )
    parser.add_option(
        "",
        "--source-language",
        dest="sourcelanguage",
        default=None,
        help="set source language code (default en-US)",
        metavar="LANG",
    )
    parser.add_option(
        "",
        "--nonrecursiveinput",
        dest="allowrecursiveinput",
        default=True,
        action="store_false",
        help="don't treat the input oo as a recursive store",
    )
    parser.add_duplicates_option()
    parser.add_multifile_option()
    parser.passthrough.append("pot")
    parser.passthrough.append("sourcelanguage")
    parser.passthrough.append("targetlanguage")
    parser.verifyoptions = verifyoptions
    parser.run(argv)


if __name__ == "__main__":
    main()
