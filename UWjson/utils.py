#!/usr/bin/env python3

version = "0.5.3"

import re, csv, itertools
from datetime import datetime, timezone, UTC

#### Default configurations

#### constants

nan = float("nan")


#### Regular expressions

Float_ID_line = r"(?i)transmission ID number\s+([0-9]+)"
Float_ID_re = re.compile(Float_ID_line)

OCR_line = r"(?i)optical irrad([0-9]+)"
OCR_re = re.compile(OCR_line)

OCR_par_line = r"(?i)optical par"
OCR_par_re = re.compile(OCR_par_line)

#### helper functions


#### main functions

def resolve_OCR(file_path):

    OCR_vals = []
    float_id = None
    val = None

    with open(file_path, "r") as infile:
        lines = infile.readlines()

    for line in lines:
        if OCR_match := OCR_re.match(line):
            if OCR_match.group(1) != val:
                val = OCR_match.group(1)
                OCR_vals.append(val)
        elif OCR_match := OCR_par_re.match(line):
            if "PAR" != val:
                val = "PAR"
                OCR_vals.append(val)        
        elif (float_match := Float_ID_re.match(line)):
            float_id = float_match.group(1)

    return (float_id, OCR_vals)


#### Script mode

if __name__=="__main__":
    
    import argparse, pathlib

    #### Script mode functions

    def iter_subdirectories(root):

        root = pathlib.Path(root)

        for p in root.rglob("*"):
            if p.is_dir():
                yield p


    # create parser; delegate to sub-parsers
    parser = argparse.ArgumentParser(description='''
        UW json decoder, utilities, version {}.
        Various utilities associated with json decoding.
    '''.format(version))
    subparsers = parser.add_subparsers(dest="command")

    # build-ocr command
    p_ocr = subparsers.add_parser(
        "build-ocr",
        help="Build table of OCR data from metadata",
    )
    p_ocr.add_argument(
        "-s", "--sort", action="store_true",
        help="whether to sort the output by float number"
    )
    p_ocr.add_argument(
        "-r", "--recursive", action="store_true",
        help="whether to descend into subfolders of IN_DIR"
    )
    p_ocr.add_argument(
        "-i", "--input", default="*.meta",
        help="input file name(s). Can be glob pattern. Default to '*.meta'"
    )
    p_ocr.add_argument(
        "-d", "--in_dir", default=".",
        help="input directory, default='.'"
    )
    p_ocr.add_argument(
        "-o", "--output", default="OcrMap.csv", metavar="OUT",
        help="output file path, default to 'OcrMap.csv'"
    )


    # parse input arguments
    args = parser.parse_args()

    # build auxiliary data file
    if args.command == "build-ocr":

        root = pathlib.Path(args.in_dir)
        out_path = pathlib.Path(args.output)

        if args.recursive:
            targets = []
            for _p in iter_subdirectories(root):
                targets = itertools.chain(targets, _p.glob(args.input))
        else:
            targets = root.glob(args.input)

        out = []

        for _x in targets:
            (float_id, ocr_vals) = resolve_OCR(_x)
            if ocr_vals:
                out.append([float_id] + ocr_vals)

        if args.sort:
            out.sort(key=lambda x: int(x[0]))

        max_channels = max(len(_x) for _x in out) - 1
        header = ["FloatId"] + ["OCR" + str(_i) for _i in range(max_channels)]

        with open(out_path, 'w', newline='', encoding='utf-8') as outfile:

            csv_writer = csv.writer(outfile)
            csv_writer.writerow(header)
            csv_writer.writerows(out)

        