#!/usr/bin/env python3

version = "0.7.0"

import operator

#### Alignment functions

def log_splitter(
    file, fill_value=None, fill_NaT=None, 
    logger=lambda x: print("[LOG] " + x)
):
    '''
    "Tokenizer" (actually, data is lightly parsed) for .log file
    Given a filename sans the .log extension, read the file and parse 
    it into an array of dictionary. Within each dictionary, the datetime
    and mission time are decoded while the calling function and the 
    message are kept as string. Keep track of any lines that have not 
    been parsed
    '''

    out_list = []
    cuts_list = []

    out = [] # output list
    cuts = [] # list of cut points
    prev_mtime = -1
    EOT_cnt = 0

    # read the entire file at once
    if isinstance(file, io.IOBase):
        lines = file.readlines()
    else:
        with open(file, "r") as infile:
            lines = infile.readlines()

    for line in lines:

        if (rx_match := log_rx.match(line)):
            
            cur_mtime = parseInt(rx_match[2], fill_value)
            entry = {
                "datetime": decode_time(rx_match[1], fill_NaT), 
                "mission_time": cur_mtime, 
                "call": rx_match[3], 
                "message": rx_match[4]
            }

            if (not isFillValue(cur_mtime, fill_value)) and (cur_mtime < prev_mtime):
                cuts.append(len(out))
            prev_mtime = cur_mtime

            out.append(entry)

        elif (rx_match := log_rx2.match(line)):
            entry = {
                "datetime": decode_time(rx_match[1], fill_NaT),
                "call": rx_match[2],
                "message": rx_match[3]
            }
            out.append(entry)

        elif line.strip() == "<EOT>":
            EOT_cnt += 1
            out_list.append(out)
            cuts_list.append(cuts)
            out = []
            cuts = []

        elif line.strip() == "":
            pass

        else:
            logger('Not decoded: "' + line + '"')

    # append the last record that possibly has no <EOT>
    if out:
        out_list.append(out)
        cuts_list.append(cuts)
        logger("Data found after the end of last <EOT>")

    # EOT check
    if EOT_cnt == 0:
        logger('"<EOT>" missing')
    elif EOT_cnt > 1:
        logger('More than 1 "<EOT>" found')

    num_out = len(out_list)
    if num_out == 1:
        out = out_list[0]
        cuts = cuts_list[0]
    elif num_out == 0:
        out = []
        cuts = []
    else:
        # find the longest record
        out_lens = [len(_x) for _x in out_list]
        max_len = 0
        max_idx = 0
        for (_i, _x) in enumerate(out_lens):
            if _x > max_len:
                max_idx = _i
                max_len = _x
        out = out_list[max_idx]
        cuts = out_list[max_idx]

    return (out, cuts)


def align_nitrate(
    msg_nitrate, isus_nitrate, direction, 
    fill_value=None, fill_NaT=None, logger=print
):

    out = []

    if direction.lower().startswith("asc"):
        msg_adv = operator.gt
    elif direction.lower().startswith("desc"):
        msg_adv = operator.lt
    else:
        logger("Incorrect specification of direction. No entry is processed.")
        return out

    more_msg = True
    more_isus = True

    tol = 1e-3
    spec_len = len(isus_nitrate[0]["packed_data"])

    msg_iter = iter(msg_nitrate)
    isus_iter = iter(isus_nitrate)

    msg = next(msg_iter)
    isus = next(isus_iter)

    while True:

        p_msg = msg["PRES"]
        p_isus = isus["CTD_depth"]

        no3_msg = msg["nitrate_onboard"]

        if isFillValue(no3_msg, fill_value):

            out.append({
                "PRES": p_msg,
                "TIME": fill_NaT,
                "nitrate_onboard": no3_msg,
                "Spectrum": [fill_value] * spec_len
            })

            try:
                msg = next(msg_iter)
            except StopIteration:
                more_msg = False
                break

        elif abs(p_msg - p_isus) < tol:
            
            out.append({
                "PRES": p_msg,
                "TIME": isus["datetime"],
                "nitrate_onboard": no3_msg,
                "Spectrum": isus["packed_data"].copy()
            })

            try:
                msg = next(msg_iter)
            except StopIteration:
                more_msg = False

            try:
                isus = next(isus_iter)
            except StopIteration:
                more_isus = False

            if (not more_msg) or (not more_isus):
                break

        elif msg_adv(p_msg, p_isus):

            out.append({
                "PRES": p_msg,
                "TIME": fill_NaT,
                "nitrate_onboard": no3_msg,
                "Spectrum": [fill_value] * spec_len
            })

            logger(f"Unmatched msg entry at PRES={p_msg}")

            try:
                msg = next(msg_iter)
            except StopIteration:
                more_msg = False
                break

        else:

            out.append({
                "PRES": isus["CTD_depth"], 
                "TIME": isus["datetime"],
                "nitrate_onboard": fill_value,
                "Spectrum": isus["packed_data"].copy()
            })

            logger(f"Unmatched isus entry at PRES={p_isus}")

            try:
                isus = next(isus_iter)
            except StopIteration:
                more_isus = False
                break

    if more_isus:

        while True:

            out.append({
                "PRES": isus["CTD_depth"], 
                "TIME": isus["datetime"],
                "nitrate_onboard": fill_value,
                "Spectrum": isus["packed_data"].copy()
            })

            logger(f"Unmatched isus entry at PRES={isus['CTD_depth']}")
            
            try:
                isus = next(isus_iter)
            except StopIteration:
                break

    if more_msg:

        while True:

            out.append({
                "PRES": msg["PRES"],
                "TIME": fill_NaT,
                "nitrate_onboard": msg["nitrate_onboard"],
                "Spectrum": [fill_value] * spec_len
            })

            logger(f"Unmatched msg entry at PRES={msg['PRES']}")

            try:
                msg = next(msg_iter)
            except StopIteration:
                break

    return out


def align_pH(
    msg_pH, dura_pH, direction, 
    fill_value=None, fill_NaT=None, logger=print
):

    out = []

    if direction.lower().startswith("asc"):
        msg_adv = operator.gt
    elif direction.lower().startswith("desc"):
        msg_adv = operator.lt
    else:
        logger("Incorrect specification of direction. No entry is processed.")
        return out

    more_msg = True
    more_dura = True
    
    tol = 1e-3

    msg_iter = iter(msg_pH)
    dura_iter = iter(dura_pH)

    msg = next(msg_iter)
    dura = next(dura_iter)

    while True:

        p_msg = msg["PRES"]
        p_dura = dura["CTD_depth"]

        pH_msg = msg["pH_V"]

        if isFillValue(pH_msg, fill_value):

            out.append({
                "PRES": p_msg,
                "TIME": fill_NaT,
                "VRS_PH": pH_msg,
                "VK_PH": fill_value
            })

            try:
                msg = next(msg_iter)
            except StopIteration:
                more_msg = False
                break

        elif abs(p_msg - p_dura) < tol:
            
            out.append({
                "PRES": p_msg,
                "TIME": dura["datetime"],
                "VRS_PH": dura["Vrs_mean"],
                "VK_PH": dura["Vk_mean"]
            })

            try:
                msg = next(msg_iter)
            except StopIteration:
                more_msg = False

            try:
                dura = next(dura_iter)
            except StopIteration:
                more_dura = False

            if (not more_msg) or (not more_dura):
                break

        elif msg_adv(p_msg, p_dura):
            
            out.append({
                "PRES": p_msg,
                "TIME": fill_NaT,
                "VRS_PH": pH_msg,
                "VK_PH": fill_value
            })

            logger(f"Unmatched msg entry at PRES={p_msg}")
            
            try:
                msg = next(msg_iter)
            except StopIteration:
                more_msg = False
                break

        else:

            out.append({
                "PRES": dura["CTD_depth"],
                "TIME": dura["datetime"],
                "VRS_PH": dura["Vrs_mean"],
                "VK_PH": dura["Vk_mean"]
            })

            logger(f"Unmatched dura entry at PRES={p_dura}")

            try:
                dura = next(dura_iter)
            except StopIteration:
                more_dura = False
                break

    if more_dura:

        while True:

            out.append({
                "PRES": dura["CTD_depth"], 
                "TIME": dura["datetime"],
                "VRS_PH": dura["Vrs_mean"],
                "VK_PH": dura["Vk_mean"]
            })

            logger(f"Unmatched dura entry at PRES={dura['CTD_depth']}")
            
            try:
                dura = next(dura_iter)
            except StopIteration:
                break

    if more_msg:

        while True:

            out.append({
                "PRES": msg["PRES"],
                "TIME": fill_NaT,
                "VRS_PH": msg["pH_V"],
                "VK_PH": fill_value
            })

            logger(f"Unmatched msg entry at PRES={p_msg}")

            try:
                msg = next(msg_iter)
            except StopIteration:
                break

    return out

