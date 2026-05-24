#!/usr/bin/env python3

'''
Version: 0.4.4
'''

import io, re, csv, itertools, operator
from datetime import datetime, timezone, UTC

#### Default configurations

# default supplemental information for output json
default_supp = {
  "DECODER_VERSION": "0.4.4",
  "SCHEMA_VERSION": "0.4.0",
  "PI": "Steven RISER",
  "OPERATING_INSTITUTION": "UW, Seattle, WA",
  "FILE_CREATION_INSTITUTION": "UW, Seattle, WA",
  "PROJECT_NAME": "Argo UW"
}

#### constants

nan = float("nan")

#### Regular expressions

# regex for parsing dimensionful numbers
dim_num_rx = re.compile(r"([+-.0-9]+)\s*([a-zA-Z]+)")

# regex for various date-time formats
mmmd_hms_y = r"[A-Z][a-z]{2}\s+[0-9]+\s+[0-9]+:[0-9]+:[0-9]+\s+[0-9]+"
mmmdy_hms = r"[A-Z][a-z]{2}\s+[0-9]+\s+[0-9]+\s+[0-9]+:[0-9]+:[0-9]+"
mmdy_hms = r"[0-9]+/[0-9]+/[0-9]+\s+[0-9]+:[0-9]+:[0-9]+"

# regex for mission header
mission_config_rx = re.compile(r"\$ Mission configuration for\s+([A-Za-z0-9]+)\(([0-9]+)\)\s+FwRev\s+([0-9]+):")

# regex for mission parameters
mission_params_rx = re.compile(r"\$ ([A-Za-z0-9]+)\((.*?)\)(?: \[(.*?)\])?")

# regex for mission generator
msg_gen_rx = re.compile(r"\$ (?:.*?)-msggen if=((?:.*?)\.msg\.bin) of=((?:.*?)\.msg)")

# regex for Profile terminated line
profile_terminated_rx = re.compile(r"\$ Profile ([0-9]+)\.([0-9]+) terminated: .*? (" + mmmd_hms_y + ")$")

# regex for detecting the start of discrete samples
discrete_sample_rx = re.compile(r"\$ Discrete samples: ([0-9]+)")

# regex for detecting the start of continuous samples
cont_header_rx = re.compile(r"#\s+" + mmmdy_hms + r"\s+Sbe41cpSerNo\[([0-9]+)\]\s+NSample\[([0-9]+)\]\s+NBin\[([0-9]+)\]")

# regex for the body of continuous samples
cont_data_rx = re.compile(r"([A-F0-9]+)(?:\[([0-9]+)\])?")

# regex for detecting the start of GPS data
gps_header_rx = re.compile(r"# GPS fix obtained in ([0-9]+)")

# regex for Iridium x, y, z coordinates
irid_geo_rx = re.compile(r"IridiumGeo: <x,y,z>:\s*([\S]+)\s+([\S]+)\s+([\S]+)\s*IrSysTime:\s*([xa-f0-9]+)$")

# regex for Iridium lat,lon coordinates
irid_fix_rx = re.compile(r"IridiumFix: <lon,lat>:\s*([\S]+)\s+([\S]+)\s*IrEpoch:\s*([0-9]+)sec\s*(" + mmdy_hms + ")")

# regex for parked sample
parkpt_rx = re.compile(r"ParkPt:\s+(" + mmmdy_hms + r")\s+([0-9]+)\s+([\S]+)\s+([\S]+)\s+([\S]+)")

# regex for parked PT, Flbb sample
parkptflbb_rx = re.compile(r"ParkPtFlbb:\s+(" + mmmdy_hms + r")\s+([0-9]+)\s+(.*)$")

# regex for Optode air-calibration data
optode_rx = re.compile(r"OptodeAirCal:\s+(" + mmmdy_hms + r")\s+([0-9]+)\s+(.*)$")

# regex for engineering parameters
engr_rx = re.compile(r"^([A-Za-z0-9]+)=(.*?)$")

# regex for element of array engineering parameters
engr_array_rx = re.compile(r"^([A-Za-z0-9]+)\[([0-9]+)\]=(.*?)$")

# regex for a generic log entry
log_rx = re.compile(r"^\((" + mmmdy_hms + r"),\s+([0-9]+)\s+sec\)\s+([_:A-Za-z0-9]+)\(?\)?\s+(.*?)$")

# regex for parsing datetime values in engineering datetime information
engr_time_rx = re.compile(r"([0-9]+)\s+(" + mmmdy_hms + ")")

# regex for profile header in .dura and .isus files
dura_header_rx = re.compile(r"Profile: ([0-9]+)\.([0-9]+) [A-Z][a-z]{2} (" + mmmd_hms_y + ")")

# regex for <EOP> line in .dura and .isus files
dura_EOP_rx = re.compile(r"<EOP>\s+:\s+([0-9]+)\.([0-9]+) [A-Z][a-z]{2} (" + mmmd_hms_y + ")")

# regex for dura and isus engineering data
dura_engr_rx = re.compile(r"^H, ([^,]+),(.*)$")

# regex to extract pressure from log during float descant
log_descent_rx = re.compile(r"\s*Pressure:\s+([0-9]+(?:\.[0-9]+))")

# regex to extract pressure from log before float starts to ascend
log_go_deep_rx = re.compile(r"\s*Sequence\s+point\s+detected\s+at\s+([0-9]+(?:\.[0-9]+))\s*dbar")

# regex to extract pressure from log during continuous profiling
log_profile_rx = re.compile(r"\s*Sample [0-9]+ initiated at ([0-9]+(?:\.[0-9]+))\s*dbar")

# regex to extract pressure from log as profile starts
log_profileinit_rx = re.compile(r"\s*PrfId:[0-9]+\s+Pressure:([0-9]+(?:\.[0-9]+))dbar")

# regex to extract piston move
log_pistonmove_rx = re.compile(
    r"([0-9]+)->([0-9]+) (?:[0-9]+\s+)*([0-9]+)\s+"
    r"\[([0-9]+)sec, ([0-9]+(?:\.[0-9]+))Volts, ([0-9]+(?:\.[0-9]+))Amps, CPT:([0-9]+)sec\]"
)


#### Utility functions

def isFillValue(val, fill_value=None):

    return (val is None) if (fill_value is None) else (val == fill_value)


def parseNaN(val, fill_value=None):
    '''
    parse a string and convert nan to None
    '''
    return fill_value if (val.strip().lower() == "nan") else val


def parseHex(val, fill_value=None):
    '''
    Parse a hexadecimal string into integer
    '''
    return fill_value if (val.strip().lower() == "nan") else int(val, 16)


def parseInt(val, fill_value=None):
    '''
    Parse an integer string into integer. nan is converted to None
    '''
    return fill_value if (val.strip().lower() == "nan") else int(val, 10)


def parseFloat(val, fill_value=None):
    '''
    Parse a floating-point number string into float. nan is converted to None
    '''
    return fill_value if (val.strip().lower() == "nan") else float(val)


def parseDimFloat(val, fill_value=None):
    '''
    Parse a string containing a floating-point value followed by unit into 
    a tuple (number, unit). If nan is encountered None is returned for 
    both number and unit. If the string does not take the expected pattern
    a ValueError is raised
    '''
    
    if val.strip().lower() == "nan": 
        return (fill_value, None)
    if (rx_match := dim_num_rx.match(val)):
        return (float(rx_match[1]), rx_match[2])
    else:
        raise ValueError("Input string does not conform to the expected pattern")


def parseDimInt(val, fill_value=None):
    '''
    Parse a string containing an integer value followed by unit into a tuple
    (number, unit). If nan is encountered None is returned for both. If the 
    string does not conform to the expected pattern a ValueError is raised.
    '''
    if val.strip() == "nan": 
        return (fill_value, None)
    if (rx_match := dim_num_rx.match(val)):
        return (int(rx_match[1]), rx_match[2])
    else:
        raise ValueError("Input string does not conform to the expected pattern")


def decode_hex(
    code, 
    jump = 0x10000, cut = 0x8000, scalar = 1, offset = 0, dp = 0, 
    fill_value=None
):
    '''
    Decode hexadecimal code into floating point values, where the code follows a 
    variation of 2's complement, with an arbitrary cut value that separates the 
    positive values from the negative values, and which the cut itself is served
    as a sentinel for non-finite values. In addition, the conversion may involve
    a scale factor `scalar`, and offset `offset`, and is rounded to `dp` decimal
    places
    '''
    # decode hex to unsigned integer
    val = int(code, 16)
        
    # out of range or non-finite values
    if cut - 1 <= val <= cut + 1:
        return fill_value

    # negative values
    elif val > cut:
        val -= jump

    return round(scalar * val + offset, dp)


def decode_if_number(value, fill_value=None):
    '''
    Decode a string IF it can be parsed as a numerical value. Integer is tried
    first and accepted if agree with the floating point representation
    '''
    if value.strip().lower() == "nan":
        return fill_value

    try:
        out1 = int(value)
    except ValueError:
        out1 = None

    try:
        out2 = float(value)
    except ValueError:
        out2 = None

    if out1 is None:
        if out2 is None:
            return value
        else:
            return out2
    else:
        if out1 == out2:
            return out1
        else:
            return out2


def decode_time(value, fill_value=None):
    '''
    Decode a string that represent calendar date time. Common formats for the 
    datetime code are tried until one that works. The resulting datetime object 
    is then recoded using the ISO 8601 standard.
    '''

    # try different format string until seeing the one that works

    if isinstance(value, str):
        try:
            value = datetime.strptime(value, "%b %d %Y %H:%M:%S")
        except ValueError:
            pass

    if isinstance(value, str):
        try:
            value = datetime.strptime(value, "%m/%d/%Y %H:%M:%S")
        except ValueError:
            pass

    if isinstance(value, str):
        try:
            value = datetime.strptime(value, "%m/%d/%Y %H%M%S")
        except ValueError:
            pass

    if isinstance(value, str):
        try:
            value = datetime.strptime(value, "%b %d %H:%M:%S %Y")
        except ValueError:
            pass

    if isinstance(value, str):
        return fill_value
    else:
        return value.isoformat() + "Z"


def dict_to_list(in_dict, fill_value=None):
    l = max(in_dict.keys())
    out = [fill_value] * (l + 1)
    for k, v in in_dict.items():
        out[k] = v
    return out


#### Component functions (for decoding specific part(s) of file/python object)

def infer_instrument(msg_dict):
    '''
    Infer the float type
    '''
    # to be further developed
    if "OptodeAirCal" in msg_dict:
        return "UW-APEX-BGC"
    else:
        return "UW-APEX-core"


def infer_positioning(msg_dict):
    '''
    Infer the mechanism for positioning the float
    '''

    if "gps" in msg_dict and msg_dict["gps"]:
        return "GPS"
    elif "Iridium" in msg_dict and msg_dict["Iridium"]:
        return "Iridium"
    else:
        return None


def parse_gps(gps_list, fill_value=None, fill_NaT=None):
    '''
    Parse GPS information
    '''
    out = []

    for entry in gps_list:
        out_entry = {}
        out_entry["description"] = "GPS_FIX"
        out_entry["TIME"] = decode_time(entry["time"], fill_NaT)
        out_entry["LATITUDE"] = parseFloat(entry["lat"], fill_value)
        out_entry["LONGITUDE"] = parseFloat(entry["lon"], fill_value)
        out_entry["sat_cnt"] = parseInt(entry["nsat"], fill_value)
        out_entry["time_to_fix"] = parseInt(entry["t_fix"], fill_value)
        out.append(out_entry)

    return out


def parse_iridium(irid_list, fill_value=None, fill_NaT=None):
    '''
    Parse Iridium information
    '''
    out = []

    for entry in irid_list:
        out_entry = {}
        out_entry["LATITUDE"] = parseFloat(entry["lat"], fill_value)
        out_entry["LONGITUDE"] = parseFloat(entry["lon"], fill_value)
        out_entry["TIME"] = decode_time(entry["time"], fill_NaT)
        out_entry["x"], unit = parseDimFloat(entry["x"], fill_value)
        assert unit == "km"
        out_entry["y"], unit = parseDimFloat(entry["y"], fill_value)
        assert unit == "km"
        out_entry["z"], unit = parseDimFloat(entry["z"], fill_value)
        assert unit == "km"
        out_entry["system_time"] = parseHex(entry["sys_time"], fill_value)
        out.append(out_entry)

    return out


def parse_engr_time(time_dict, fill_NaT=None):
    '''
    Parse timestamp information in engineering data
    '''

    out = {}

    rx_match = engr_time_rx.match(time_dict.get('TimeStartDescent', ""))
    if rx_match: 
        out["StartDescent"] = decode_time(rx_match[2], fill_NaT)

    rx_match = engr_time_rx.match(time_dict.get('TimeStartPark', ""))
    if rx_match: 
        out["StartPark"] = decode_time(rx_match[2], fill_NaT)

    rx_match = engr_time_rx.match(time_dict.get('TimeStartProfileDescent', ""))
    if rx_match: 
        out["StartProfileDescent"] = decode_time(rx_match[2], fill_NaT)

    rx_match = engr_time_rx.match(time_dict.get('TimeStartProfile', ""))
    if rx_match: 
        out["StartProfile"] = decode_time(rx_match[2], fill_NaT)

    rx_match = engr_time_rx.match(time_dict.get('TimeStopProfile', ""))
    if rx_match: 
        out["StopProfile"] = decode_time(rx_match[2], fill_NaT)

    rx_match = engr_time_rx.match(time_dict.get('TimeStartTelemetry', ""))
    if rx_match: 
        out["StartTelemetry"] = decode_time(rx_match[2], fill_NaT)

    return out


def parse_discrete(disc_dict, OCR_map=None, fill_value=None, logger=print):
    '''
    Parse discrete CTD samples of the float
    '''
    out = {}
    CTD = []
    Optode = []
    NO3 = []
    pH = []
    FLBB = []
    OCR = []

    if len(disc_dict["headers"]) == 3: # core CTD data only
        for item in itertools.chain(disc_dict["park_data"], disc_dict["data"]):
            CTD.append({
                "PRES": parseFloat(item["p"], fill_value),
                "TEMP": parseFloat(item["t"], fill_value),
                "PSAL": parseFloat(item["s"], fill_value)
            })

    elif len(disc_dict["headers"]) == 15: # CTD(3) + optode(3) + nitrate(2) + FLBB(3) + OCR(4)
        for item in itertools.chain(disc_dict["park_data"], disc_dict["data"]):
            p = parseFloat(item["p"], fill_value)
            CTD.append({
                "PRES": p, 
                "TEMP": parseFloat(item["t"], fill_value), 
                "PSAL": parseFloat(item["s"], fill_value)
            })
            Optode.append({
                "PRES": p, 
                "Temp_optode": parseFloat(item["Topt"], fill_value), 
                "TPhase": parseFloat(item["TPhase"], fill_value), 
                "RPhase": parseFloat(item["RPhase"], fill_value)
            })
            NO3.append({
                "PRES": p, 
                "nitrate_onboard": parseFloat(item["no3"], fill_value)
            })
            pH.append({
                "PRES": p, 
                "pH_V": parseFloat(item["pH(V)"], fill_value)
            })
            FLBB.append({
                "PRES": p, 
                "FLUORESCENCE_CHLA": parseInt(item["FSig"], fill_value), 
                "BETA_BACKSCATTERING700": parseInt(item["BbSig"], fill_value), 
                "temp_signal": parseInt(item["TSig"], fill_value)
            })

            if OCR_map is None:
                OCR0 = "OCR0"
                OCR1 = "OCR1"
                OCR2 = "OCR2"
                OCR3 = "OCR3"
            else:
                OCR0 = "RAW_DOWNWELLING_IRRADIANCE" + OCR_map["OCR0"]
                OCR1 = "RAW_DOWNWELLING_IRRADIANCE" + OCR_map["OCR1"]
                OCR2 = "RAW_DOWNWELLING_IRRADIANCE" + OCR_map["OCR2"]
                if OCR_map["OCR3"] == "PAR":
                    OCR3 = "RAW_DOWNWELLING_IRRADIANCE_PAR"
                else:
                    OCR3 = "RAW_DOWNWELLING_IRRADIANCE" + OCR_map["OCR3"]
            OCR.append({
                "PRES": p, 
                OCR0: parseHex(item["Ocr[0]"], fill_value), 
                OCR1: parseHex(item["Ocr[1]"], fill_value),
                OCR2: parseHex(item["Ocr[2]"], fill_value), 
                OCR3: parseHex(item["Ocr[3]"], fill_value)
            })

    else:
        logger("Unknown data fields. No entries returned")

    if CTD:
        out["CTD"] = CTD
    if Optode:
        out["Optodo"] = Optode
    if NO3:
        out["NO3"] = NO3
    if pH:
        out["pH"] = pH
    if FLBB:
        out["FLBB"] = FLBB
    if OCR:
        out["OCR"] = OCR

    return out


def parse_continuous(cont_dict, sort=None, fill_value=None, logger=print):
    '''
    Parse continuous CTD samples of the float
    '''

    out = []

    if cont_dict["hex_len"] == 14:

        for item in cont_dict["data"]:

            if item == "0" * 14: continue

            tmp = {}
            tmp["PRES"] = decode_hex(
                item[:4], cut = 0xf000, scalar = 0.1, dp = 1, 
                fill_value = fill_value
            )
            tmp["TEMP"] = decode_hex(
                item[4:8], cut = 0xf000, scalar = 0.001, dp = 3, 
                fill_value = fill_value
            )
            tmp["PSAL"] = decode_hex(
                item[8:12], cut = 0xf000, scalar = 0.001, dp = 3, 
                fill_value = fill_value
            )
            tmp["n_samp"] = decode_hex(item[12:], fill_value = fill_value)

            out.append(tmp)

    else:
        logger("Unknown hex legnth. No entries returned")
        return out

    if sort is None:
        pass
    elif sort.lower().startswith("asc"):
        out.sort(key=lambda x: -x["PRES"])
    elif sort.lower().startswith("desc"):
        out.sort(key=lambda x: x["PRES"])

    return out


def parse_parked(
    park_dict, meas_type, 
    fill_value=None, fill_NaT=None, logger=print
):
    '''
    Parse parked CTD samples of the float
    '''
    out = {}

    CTD = []
    FLBB = []
    Traj = []

    if meas_type == "ParkPt":

        for item in park_dict:

            p = parseFloat(item["p"], fill_value)
            T = parseFloat(item["t"], fill_value)
            t = decode_time(item["time"], fill_NaT)
            
            CTD.append({
                "PRES": p,
                "TEMP": T,
                "TIME": t
            })
            Traj.append({
                "TIME": t,
                "PRES": p
            })

    elif meas_type == "ParkPtFlbb":

        for item in park_dict:

            p = parseFloat(item["p"], fill_value)
            T = parseFloat(item["t"], fill_value)
            t = decode_time(item["time"], fill_NaT)

            CTD.append({
                "PRES": p,
                "TEMP": T,
                "TIME": t
            })
            Traj.append({
                "TIME": t,
                "PRES": p
            })
            FLBB.append({
                "PRES": p,
                "FSig": parseInt(item["FSig"], fill_value),
                "BbSig": parseInt(item["BbSig"], fill_value),
                "TSig": parseInt(item["TSig"], fill_value),
                "TIME": t
            })

    else:
        logger("Unknown measurement type. No entries returned")

    if CTD:
        out["CTD"] = CTD
    if Traj:
        out["Traj"] = Traj
    if FLBB:
        out["FLBB"] = FLBB

    return out


def parse_OptodeAirCal(optode_list, fill_value=None, fill_NaT=None):

    out = []
    for item in optode_list:
        out.append({
            "Pres_air": parseInt(item["AirP"], fill_value),
            "Pres_CTD": parseFloat(item["p"], fill_value),
            "Temp_optode": parseFloat(item["optodeT"], fill_value),
            "TPhase": parseFloat(item["TPhase"], fill_value),
            "RPhase": parseFloat(item["RPhase"], fill_value),
            "FSig": parseInt(item["FSig"], fill_value),
            "BbSig": parseInt(item["BbSig"], fill_value),
            "TSig": parseInt(item["TSig"], fill_value),
            "Ocr": [
                parseHex(item["Ocr[0]"], fill_value),
                parseHex(item["Ocr[1]"], fill_value),
                parseHex(item["Ocr[2]"], fill_value),
                parseHex(item["Ocr[3]"], fill_value),
            ],
            "TIME": decode_time(item["time"], fill_NaT)
        })
    return out


def parse_mission_config(config_dict):
    '''
    Parse mission configuration data

    WARNING: the input dictionary is modified in place and returned
    '''

    if "AtDialCmd" in config_dict:
        config_dict["AtDialCmd"] = { "value": config_dict["AtDialCmd"]["value"] }
    if "AltDialCmd" in config_dict:
        config_dict["AltDialCmd"] = { "value": config_dict["AltDialCmd"]["value"] }

    return config_dict


def parse_engineering_data(engr_list):
    '''
    Parse engineering data

    WARNING: the input list is modified in place and returned
    '''

    for engr_dict in engr_list:
        
        for k, v in engr_dict.items():

            if isinstance(v, dict):
                engr_dict[k] = dict_to_list(v)

    return engr_list


def parse_OCR_map(file):

    out = {}
    need_close = False

    if isinstance(file, io.IOBase):
        infile = file
        need_close = False
    else:
        infile = open(file, "r")
        need_close = True

    try:
        csv_reader = csv.reader(infile)
        top_row = next(csv_reader)
        header = top_row[1:]

        for row in csv_reader:
            out[int(row[0])] = {
                _x : _y for _x, _y 
                in zip(header, row[1:])
            }

    finally:
        if need_close: infile.close()

    return out


def parse_AOML_ID_map(file, logger=print):
    '''
    Construct mapping between internal float ID to AOML ID using the 
    AomlIdMap file
    '''
    out_dict = {}
    Apf_set = set()
    Aoml_set = set()

    if isinstance(file, io.IOBase):
        line_list = file.readlines()
    else:
        with open(file, "r") as infile:
            line_list = infile.readlines()

    for i, line in enumerate(line_list, 1):
        line = line.strip()
        if (not line.startswith("#")) and (not line.startswith("//")):

            entries = line.split()

            try:
                AOML_Id = entries[0]
            except IndexError:
                continue
            try:
                AOML_Id = int(AOML_Id)
            except ValueError:
                logger(f"Line {i}: WARNING: non-integer value AOML ID '{AOML_Id}'")

            if AOML_Id in Aoml_set:
                logger(f"Line {i}: WARNING: multiple occurrence of AOML ID {AOML_Id}")
            Aoml_set.add(AOML_Id)

            try:
                Apf_Id = entries[1]
            except IndexError:
                # ignore unassigned numbers
                #logger(f"Line {i}: WARNING: unassigned AOML ID {AOML_Id}")
                continue
            if Apf_Id.startswith("#") or Apf_Id.startswith("//"):
                # ignore unassigned numbers
                #logger(f"Line {i}: WARNING: unassigned AOML ID {AOML_Id}")
                continue

            try:
                Apf_Id = int(Apf_Id)
            except ValueError:
                logger(f"Line {i}: WARNING: non-integer value Apf ID '{Apf_Id}'")

            if Apf_Id in Apf_set:
                logger(f"Line {i}: WARNING: multiple occurrence of Apf ID {Apf_Id}")
            Apf_set.add(Apf_Id)

            out_dict[Apf_Id] = AOML_Id

    return out_dict


def parse_WMO_ID_map(file, logger=print):
    '''
    Construct mapping between internal float ID to WMO ID using the 
    WmoIdMap file
    '''
    out_dict = {}
    Apf_set = set()
    Wmo_set = set()

    if isinstance(file, io.IOBase):
        line_list = file.readlines()
    else:
        with open(file, "r") as infile:
            line_list = infile.readlines()

    for i, line in enumerate(line_list, 1):
        line = line.strip()
        if (not line.startswith("#")) and (not line.startswith("//")):

            entries = line.split()

            try:
                WMO_Id = entries[0]
            except IndexError:
                continue

            try:
                WMO_Id = int(WMO_Id)
            except ValueError:
                logger(f"Line {i}: WARNING: non-integer value WMO ID '{WMO_Id}'")

            if WMO_Id in Wmo_set:
                logger(f"Line {i}: WARNING: multiple occurrence of WMO ID {WMO_Id}")
            Wmo_set.add(WMO_Id)

            try:
                Apf_Id = entries[1]
            except IndexError:
                # ignore unassigned numbers
                #logger(f"Line {i}: WARNING: unassigned WMO ID {WMO_Id}")
                continue

            if Apf_Id.startswith("#") or Apf_Id.startswith("//"):
                # ignore unassigned numbers
                #logger(f"Line {i}: WARNING: unassigned WMO ID {WMO_Id}")
                continue

            try:
                Apf_Id = int(Apf_Id)
            except ValueError:
                logger(f"Line {i}: WARNING: non-integer value Apf ID '{Apf_Id}'")

            if Apf_Id in Apf_set:
                logger(f"Line {i}: WARNING: multiple occurrence of Apf ID {Apf_Id}")
            Apf_set.add(Apf_Id)

            out_dict[Apf_Id] = WMO_Id

    return out_dict


def parse_dura_science(line, dura_type, fill_value=None, fill_NaT=None, logger=print):

    out = {}

    vals = line.split(",")
    assert len(vals) == 22

    out["CRC"] = vals[0]
    out["ID"] = vals[1]
    out["datetime"] = decode_time(vals[2], fill_NaT)
    out["CTD_depth"] = parseFloat(vals[4], fill_value)
    out["CTD_temp"] = parseFloat(vals[5], fill_value)
    out["CTD_salinity"] = parseFloat(vals[6], fill_value)
    out["sample_counter"] = parseInt(vals[7], fill_value)
    out["power_cycle_counter"] = parseInt(vals[8], fill_value)
    out["error_counter"] = parseInt(vals[9], fill_value)
    out["housing_temp"] = parseFloat(vals[10], fill_value)
    out["housing_humidity"] = parseFloat(vals[11], fill_value)
    out["input_voltage"] = parseFloat(vals[12], fill_value)
    out["input_current"] = parseFloat(vals[13], fill_value)
    out["foobar_pH"] = parseFloat(vals[14], fill_value)
    out["backup_battery_V"] = parseFloat(vals[15], fill_value)
    out["Vrs_mean"] = parseFloat(vals[16], fill_value)
    out["Vrs_stdev"] = parseFloat(vals[17], fill_value)
    out["Vk_mean"] = parseFloat(vals[18], fill_value)
    out["Vk_stdev"] = parseFloat(vals[19], fill_value)
    if dura_type=="MSC3":
        out["lk"] = 1e-9 * parseFloat(vals[20], fill_value)
        out["lb"] = 1e-9 * parseFloat(vals[21], fill_value)
    elif dura_type=="MSC1":
        out["lk"] = parseFloat(vals[20], fill_value)
        out["lb"] = parseFloat(vals[21], fill_value)
    else:
        raise ValueError(f'Unknown dura_type "{dura_type}"')

    return out


def parse_isus_science(line, fill_value=None, fill_NaT=None, logger=print):

    out = {}

    vals = line.split(",")
    assert len(vals) == 26

    out["CRC"] = vals[0]
    out["ID"] = vals[1]
    out["datetime"] = decode_time(vals[2], fill_NaT)
    out["CTD_depth"] = parseFloat(vals[4], fill_value)
    out["CTD_temp"] = parseFloat(vals[5], fill_value)
    out["CTD_salinity"] = parseFloat(vals[6], fill_value)
    out["sample_counter"] = parseInt(vals[7], fill_value)
    out["POR_counter"] = parseInt(vals[8], fill_value)
    out["isus_error_counter"] = parseInt(vals[9], fill_value)
    out["sys_error_counter"] = parseInt(vals[10], fill_value)
    out["housing_temp"] = parseFloat(vals[11], fill_value)
    out["housing_humidity"] = parseFloat(vals[12], fill_value)
    out["input_voltage"] = parseFloat(vals[13], fill_value)
    out["input_current"] = parseFloat(vals[14], fill_value)
    out["max_lamp_intensity"] = parseFloat(vals[15], fill_value)
    out["min_lamp_intensity"] = parseFloat(vals[16], fill_value)
    out["DC_mean"] = parseFloat(vals[17], fill_value)
    out["DC_stdev"] = parseFloat(vals[18], fill_value)
    out["isus_salinity"] = parseFloat(vals[19], fill_value)
    out["isus_nitrate"] = parseFloat(vals[20], fill_value)
    out["fit_error"] = parseFloat(vals[21], fill_value)
    out["data_pixel_begin"] = parseInt(vals[22], fill_value)
    out["data_pixel_end"] = parseInt(vals[23], fill_value)
    out["DC_sw"] = parseFloat(vals[25], fill_value)

    hex_str = vals[24]
    packed = [parseHex(hex_str[i:i+4], fill_value) for i in range(0, len(hex_str), 4)]
    assert len(packed) == out["data_pixel_end"] - out["data_pixel_begin"] + 1

    out["packed_data"] = packed

    return out


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

            logger(f"Unmatched isus entry at PRES={isus["CTD_depth"]}")
            
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

            logger(f"Unmatched msg entry at PRES={msg["PRES"]}")

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

            logger(f"Unmatched dura entry at PRES={dura["CTD_depth"]}")
            
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


def log_extractor(log, fill_value = None):

    fall = []
    rise = []
    piston = []
    
    for entry in log:

        match entry["call"].strip().lower():
            
            case "descent":

                rx_match = log_descent_rx.match(entry["message"])
                if rx_match:
                    pres = float(rx_match[1])
                    fall.append({
                        "TIME": entry["datetime"], 
                        "PRES": pres, 
                        "description": "Descent"
                    })

            case "godeep":
            
                rx_match = log_go_deep_rx.match(entry["message"])
                if rx_match:
                    pres = float(rx_match[1])
                    rise.append({
                        "TIME": entry["datetime"], 
                        "PRES": pres, 
                        "description": "Sequence point"
                    })

            case "profileinit":

                rx_match = log_profileinit_rx.match(entry["message"])
                if rx_match:
                    pres = float(rx_match[1])
                    rise.append({
                        "TIME": entry["datetime"], 
                        "PRES": pres, 
                        "description": "Profile Init"
                    })
            
            case "profile":

                rx_match = log_profile_rx.match(entry["message"])
                if rx_match:
                    pres = float(rx_match[1])
                    rise.append({
                        "TIME": entry["datetime"], 
                        "PRES": pres, 
                        "description": "Profile"
                    })

            case "pistonmoveabswto":
                
                rx_match = log_pistonmove_rx.match(entry["message"])
                if rx_match:
                    pstart = int(rx_match[1])
                    ptarget = int(rx_match[2])
                    pend = int(rx_match[3])
                    current = float(rx_match[6])
                    voltage = float(rx_match[5])
                    time = int(rx_match[4])
                    piston.append({
                        "TIME": entry["datetime"],
                        "piston_start": pstart, 
                        "piston_target": ptarget, 
                        "piston_end": pend,
                        "current": current, 
                        "voltage": voltage, 
                        "duration": time
                    })
                   
    return {"Fall": fall, "Rise": rise, "Piston": piston}


#### conglomerate functions

def msg_tokenizer(file, logger=lambda x: print("[MSG] " + x)):
    '''
    "Tokenizer" for .msg files. Given a filename sans the .msg extension, 
    read the file and parse it into a dictionary of strings. Keep track of any 
    lines that have not been parsed or any keys that are overwritten
    '''

    out = {} # output dictionary
    stage = 0
    EOT_cnt = 0
    mission_config = {}
    engineering_data = []
    engineering_sect = {}
    gps_sect = {}
    iridium_sect = {}

    # read the entire file at once
    if isinstance(file, io.IOBase):
        lines = file.readlines()
    else:
        with open(file, "r") as infile:
            lines = infile.readlines()

    lines_iter = iter(lines)

    try:
        # parse line by line
        line = next(lines_iter).rstrip()
        while True:

            if line.strip() == "<EOT>":
                if engineering_sect:
                    engineering_data.append(engineering_sect)
                    engineering_sect = {}
                if gps_sect:
                    if "gps" not in out:
                        out["gps"] = []
                    out["gps"].append(gps_sect)
                    gps_sect = {}
                if iridium_sect:
                    if "Iridium" not in out:
                        out["Iridium"] = []
                    out["Iridium"].append(iridium_sect)
                    iridium_sect = {}
                EOT_cnt += 1

            # mission config lines
            elif line.startswith("$"):

                if (rx_match := mission_params_rx.match(line)):
                    key = rx_match[1]
                    if key in mission_config:
                        logger('Duplicated key: "' + key + '"')
                    if stage != 1:
                        logger('Mission parameter at wrong stage:' + line)
                    if rx_match[3] is None:
                        mission_config[key] = { "value": rx_match[2] }
                    else:
                        mission_config[key] = { "value": rx_match[2], "unit": rx_match[3] }

                elif (rx_match := mission_config_rx.match(line)):
                    if "model" in mission_config:
                        logger('Duplicated key: "mission_config"')
                    stage = 1
                    mission_config["model"] = { "value": rx_match[1] }
                    mission_config["Id"] = { "value": rx_match[2] }
                    mission_config["FwRev"] = { "value": rx_match[3] }

                elif (line.startswith("$ SBD MSG Generator")):
                    pass

                elif (line.startswith("$ $Revision$ $Date$")):
                    pass

                elif (rx_match := msg_gen_rx.match(line)):
                    out["bin_msg_file:"] = rx_match[1]
                    out["msg_file:"] = rx_match[2]

                elif (rx_match := profile_terminated_rx.match(line)):
                    if "profile_terminated" in out:
                        logger('Duplicated key: "profile_terminated"')
                    out["profile_terminated"] = {
                        "FloatId": rx_match[1], 
                        "ProfileID": rx_match[2], 
                        "time": rx_match[3]
                    }

                elif (rx_match := discrete_sample_rx.match(line)):
                    stage = 2
                    if "discrete_samples" in out:
                        logger('Duplicated key: "discrete_samples"')
                    
                    discrete = {"N": rx_match[1]}
                    park_data = []
                    data = []

                    # reading header of discrete samples
                    line = next(lines_iter).rstrip()
                    headers = line.split()[1:]

                    # reading discrete samples
                    line = next(lines_iter).rstrip()
                    while line.startswith("  "):
                        n = len(headers)
                        values = line.split(maxsplit=n)
                        entry = {}
                        for _i, _name in enumerate(headers):
                            entry[_name] = values[_i]
                        if line.strip().endswith("(Park Sample)"):
                            park_data.append(entry)
                        else:
                            data.append(entry)
                        line = next(lines_iter).rstrip()

                    # pack the results
                    discrete["headers"] = headers
                    discrete["park_data"] = park_data
                    discrete["data"] = data
                    out["discrete_samples"] = discrete

                    # rewind one element
                    lines_iter = itertools.chain([line], lines_iter)

                elif line.strip() == "$":
                    if stage == 1:
                        stage = 2 # single '$' indicates that mission parameters record ended

                else:
                    logger('Not decoded: "' + line + '"')

            elif line.startswith("#"):
                
                if (rx_match := cont_header_rx.match(line)):

                    if "cont_samples" in out:
                        logger('Duplicated key: "cont_samples"')

                    if stage != 2:
                        logger('Science data at wrong stage:' + line)
                        
                    continuous = {
                        "SerNo": rx_match[1], 
                        "NSample": rx_match[2], 
                        "NBin": rx_match[3]
                    }
                    data = []

                    line = next(lines_iter).rstrip()

                    # detect the length of hex data
                    rx_match = cont_data_rx.match(line)
                    continuous["hex_len"] = len(rx_match[1])
                    
                    while (rx_match := cont_data_rx.match(line)):

                        if (k := rx_match[2]) is not None:
                            for _i in range(int(k)):
                                data.append(rx_match[1])
                        else:
                            data.append(rx_match[1])
                        
                        line = next(lines_iter).rstrip()

                    # pack the result
                    continuous["data"] = data
                    out["cont_samples"] = continuous

                    # rewind one element
                    lines_iter = itertools.chain([line], lines_iter)

                elif (rx_match := gps_header_rx.match(line)):

                    stage = 3 # gps data marks the start of engineering data section

                    if gps_sect:
                        logger('Duplicated key: "gps"')

                    line = next(lines_iter).rstrip()
                    if line.startswith("#"):
                        line = next(lines_iter).rstrip()
                    values = line.split()
                    gps_sect = { 
                        "lon": values[1], "lat": values[2], 
                        "time": values[3] + " " + values[4],
                        "nsat": values[5], "t_fix": rx_match[1]
                    }

                elif line.startswith("# Attempt to get GPS fix failed"):
                    pass

                else:
                    logger('Not decoded: "' + line + '"')

            elif line.startswith("Iridium"):

                stage = 3 # Iridium data marks the start of engineering data section

                if (rx_match := irid_geo_rx.match(line)):
                    geo = {"x": rx_match[1], "y": rx_match[2], "z": rx_match[3], "sys_time": rx_match[4]}
                    if {"x", "y", "z", "sys_time"} & iridium_sect.keys():
                        logger('Duplicated key: "Iridium"')
                    iridium_sect |= geo

                elif (rx_match := irid_fix_rx.match(line)):
                    fix = {
                        "lon": rx_match[1], "lat": rx_match[2], 
                        "epoch": rx_match[3], "time": rx_match[4]
                    }
                    if {"lon", "lat", "time", "epoch"} & iridium_sect.keys():
                        logger('Duplicated key: "Iridium"')
                    iridium_sect |= fix

                else:
                     logger('Not decoded: "' + line + '"')

            elif "=" in line and stage == 3:

                if (rx_match := engr_rx.match(line)):
                    if rx_match[1] in engineering_sect:
                        logger('Duplicated key:"' + rx_match[1] + '"')

                    engineering_sect[rx_match[1]] = rx_match[2]

                elif (rx_match := engr_array_rx.match(line)):
                    if rx_match[1] in engineering_sect:
                        if rx_match[2] in engineering_sect[rx_match[1]]:
                            logger('Duplicated key:"' + rx_match[1] + '"')
                        engineering_sect[rx_match[1]] |= {int(rx_match[2]): rx_match[3]}
                    else:
                        engineering_sect[rx_match[1]] = {int(rx_match[2]): rx_match[3]}

                else:
                    logger('Not decoded: "' + line + '"')

            elif (rx_match := parkpt_rx.match(line)):
                parkpt = {
                    "time": rx_match[1], "epoch": rx_match[2], "mtime": rx_match[3], 
                    "p": rx_match[4], "t": rx_match[5]
                }
                if "ParkPt" in out:
                    out["ParkPt"].append(parkpt)
                else:
                    out["ParkPt"] = [ parkpt ]

            elif (rx_match := parkptflbb_rx.match(line)):
                nums = rx_match[3].split()
                parkpt = {
                    "time": rx_match[1], "epoch": rx_match[2], "mtime": nums[0],
                    "p": nums[1], "t": nums[2], 
                    "FSig": nums[3], "BbSig": nums[4], "TSig": nums[5]
                }
                if "ParkPtFlbb" in out:
                    out["ParkPtFlbb"].append(parkpt)
                else:
                    out["ParkPtFlbb"] = [ parkpt ]

            elif (rx_match := optode_rx.match(line)):
                nums = rx_match[3].split()
                optode = {
                    "time": rx_match[1], "epoch": rx_match[2], 
                    "AirP": nums[0], "p": nums[1], "optodeT": nums[2], 
                    "TPhase": nums[3], "RPhase": nums[4],
                    "FSig": nums[5], "BbSig": nums[6], "TSig": nums[7],
                    "Ocr[0]": nums[8], "Ocr[1]": nums[9], "Ocr[2]": nums[10], "Ocr[3]": nums[11]
                }
                if "OptodeAirCal" in out:
                    out["OptodeAirCal"].append(optode)
                else:
                    out["OptodeAirCal"] = [ optode ]
            elif line.strip() == "":
                pass # OK to skip line

            else:
                logger('Not decoded: "' + line + '"')

            line = next(lines_iter).rstrip()

    except StopIteration:
        if engineering_sect:
            engineering_data.append(engineering_sect)
            engineering_sect = {}
            logger('Engineering data after last "<EOT>"')
        if gps_sect:
            if "gps" not in out:
                out["gps"] = []
            out["gps"].append(gps_sect)
            gps_sect = {}
            logger('GPS data after last "<EOT>"')
        if iridium_sect:
            if "Iridium" not in out:
                out["Iridium"] = []
            out["Iridium"].append(iridium_sect)
            iridium_sect = {}
            logger('Iridium data after last "<EOT>"')

    # consolidate data
    out["mission_config"] = mission_config
    out["engineering_data"] = engineering_data

    # EOT check
    if EOT_cnt == 0:
        logger('"<EOT>" missing')
    elif EOT_cnt > 1:
        logger('More than 1 "<EOT>" found')

    return out


def log_tokenizer(
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

    out = [] # output list
    cuts = [] # list of cut points
    prev_mtime = -1

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

        elif line.strip() == "" or line.strip() == "<EOT>":
            pass

        else:
            logger('Not decoded: "' + line + '"')

    return (out, cuts)


def dura_tokenizer(
    file, dura_type, fill_value=None, fill_NaT=None, 
    logger=lambda x: print("[DURA] " + x)
):

    out_list = []
    out = {} # output dictionary
    stage = 0
    EOP_cnt = 0
    EOT_cnt = 0
    engr_list = []
    engr_dict = {}
    sci_data = []

    # read the entire file at once
    if isinstance(file, io.IOBase):
        lines = file.readlines()
    else:
        with open(file, "r") as infile:
            lines = infile.readlines()

    lines_iter = iter(lines)

    try:
        # parse line by line
        line = next(lines_iter).rstrip()
        while True:

            if (rx_match := dura_engr_rx.match(line)):

                key = rx_match[1].strip()
                val = rx_match[2].strip()

                if stage != 1 and stage != 3:
                    logger(f'Engineering data at the wrong stage (={stage})')
                if key in engr_dict:
                    logger(f'Duplicated engineering data key: "{key}"')
                engr_dict[key] = val

            elif line.startswith("0x"):

                if stage == 1:
                    stage = 2
                if stage != 2:
                    logger(f'Science data at the wrong stage (={stage})')

                sci_data.append(
                    parse_dura_science(line, dura_type, fill_value, fill_NaT, logger)
                )

            elif (rx_match := dura_header_rx.match(line)):

                if "Id" in engr_dict:
                    logger('Duplicated key: "Id"')
                if stage != 0:
                    logger(f"Header at the wrong stage (={stage})")
                stage = 1 # advance stage for next line
                engr_dict["Id"] = parseInt(rx_match[1], fill_value)
                engr_dict["ProfileId"] = parseInt(rx_match[2], fill_value)
                engr_dict["Timestamp"] = decode_time(rx_match[3], fill_NaT)

            elif (rx_match := dura_EOP_rx.match(line)):
                EOP_cnt += 1
                engr_list.append(engr_dict)
                engr_dict = {}
                engr_dict["Id"] = parseInt(rx_match[1], fill_value)
                engr_dict["ProfileId"] = parseInt(rx_match[2], fill_value)
                engr_dict["Timestamp"] = decode_time(rx_match[3], fill_NaT)
                stage = 3 # advance stage

            elif line.strip() == "":
                pass

            elif line.strip() == "# No error records to log.":
                pass

            elif line.strip() == "<EOT>":

                EOT_cnt += 1
                stage = 0

                engr_list.append(engr_dict)
                out["science_data"] = sci_data
                out["engineering_data"] = engr_list
                out_list.append(out)
                out = {}
                engr_list = []
                engr_dict = {}
                sci_data = []

            else:
                logger('Not decoded: "' + line + '"')

            line = next(lines_iter).rstrip()

    except StopIteration:
        pass

    # EOT check
    if EOT_cnt == 0:
        logger('"<EOT>" missing')
    elif EOT_cnt > 1:
        logger('More than 1 "<EOT>" found')

    return out_list[-1]


def isus_tokenizer(
    file, fill_value=None, fill_NaT=None, 
    logger=lambda x: print("[ISUS] " + x)
):

    out_list = []
    out = {} # output dictionary
    stage = 0
    EOP_cnt = 0
    EOT_cnt = 0
    engr_list = []
    engr_dict = {}
    sci_data = []

    # read the entire file at once
    if isinstance(file, io.IOBase):
        lines = file.readlines()
    else:
        with open(file, "r") as infile:
            lines = infile.readlines()

    lines_iter = iter(lines)

    try:
        # parse line by line
        line = next(lines_iter).rstrip()
        while True:

            if (rx_match := dura_engr_rx.match(line)):

                key = rx_match[1].strip()
                val = rx_match[2].strip()

                if stage != 1 and stage != 3:
                    logger(f'Engineering data at the wrong stage (={stage})')
                if key in engr_dict:
                    logger(f'Duplicated engineering data key: "{key}"')
                engr_dict[key] = val

            elif line.startswith("0x"):
                if stage == 1:
                    stage = 2
                if stage != 2:
                    logger(f'Science data at the wrong stage (={stage})')

                sci_data.append(parse_isus_science(line, fill_value, fill_NaT, logger))

            elif (rx_match := dura_header_rx.match(line)):

                if "Id" in engr_dict:
                    logger('Duplicated key: "Id"')
                if stage != 0:
                    logger(f"Header at the wrong stage (={stage})")
                stage = 1 # advance stage for next line
                engr_dict["Id"] = parseInt(rx_match[1], fill_value)
                engr_dict["ProfileId"] = parseInt(rx_match[2], fill_value)
                engr_dict["Timestamp"] = decode_time(rx_match[3], fill_NaT)

            elif (rx_match := dura_EOP_rx.match(line)):
                EOP_cnt += 1
                engr_list.append(engr_dict)
                engr_dict = {}
                engr_dict["Id"] = parseInt(rx_match[1], fill_value)
                engr_dict["ProfileId"] = parseInt(rx_match[2], fill_value)
                engr_dict["Timestamp"] = decode_time(rx_match[3], fill_NaT)
                stage = 3 # advance stage

            elif line.strip() == "":
                pass

            elif line.strip() == "# No error records to log.":
                pass

            elif line.strip() == "<EOT>":
                EOT_cnt += 1
                stage = 0

                engr_list.append(engr_dict)
                out["science_data"] = sci_data
                out["engineering_data"] = engr_list
                out_list.append(out)
                out = {}
                engr_list = []
                engr_dict = {}
                sci_data = []

            else:
                logger('Not decoded: "' + line + '"')

            line = next(lines_iter).rstrip()

    except StopIteration:
        pass

    # EOT check
    if EOT_cnt == 0:
        logger('"<EOT>" missing')
    elif EOT_cnt > 1:
        logger('More than 1 "<EOT>" found')

    return out_list[-1]


#### overall parser

def L0_parser(
    msg_dict, log_dict, dura_dict, isus_dict, cp_dict, 
    AOML_map, WMO_map, OCR_map,
    supp_dict=None, consume=False, 
    fill_value=None, fill_NaT=None, logger=print
):
    '''
    Parser for L0 json
    
    Warning: the input msg_dict and log_dict may be modified in-place. 
    Use defensive copy if needed
    '''

    if supp_dict is None:
        supp_dict = default_supp.copy()

    config_dict = msg_dict.get("mission_config", {})
    engr_list = msg_dict.get("engineering_data", [{}])
    engr_dict = engr_list[-1]

    out_dict = {}

    # In general, prefer to extract info from engineering data as opposed to mission config
    # general header information
    t_string = datetime.now(UTC).replace(microsecond=0).isoformat()[:-6] + "Z"
    float_id = int(engr_dict["FloatId"])
    out_dict["FILE_CREATION_DATE"] = t_string
    out_dict["FILE_UPDATE_DATE"] = t_string
    out_dict["DECODER_VERSION"] = supp_dict["DECODER_VERSION"]
    out_dict["SCHEMA_VERSION"] = supp_dict["SCHEMA_VERSION"]
    out_dict["INTERNAL_ID_NUMBER"] = float_id
    out_dict["TRANSMISSION_ID_NUMBER"] = float_id
    out_dict["AOML_ID_NUMBER"] = AOML_map[float_id]
    out_dict["WMO_ID_NUMBER"] = WMO_map[float_id]
    out_dict["INSTRUMENT_TYPE"] = infer_instrument(msg_dict)
    out_dict["OPERATING_INSTITUTION"] = supp_dict["OPERATING_INSTITUTION"]
    out_dict["FILE_CREATION_INSTITUTION"] = supp_dict["FILE_CREATION_INSTITUTION"]
    out_dict["PI"] = supp_dict["PI"]
    out_dict["PROJECT_NAME"] = supp_dict["PROJECT_NAME"]
    out_dict["CYCLE_NUMBER"] = int(engr_dict["ProfileId"], 10)
    out_dict["POSITIONING_SYSTEM"] = infer_positioning(msg_dict)

    # interpreting mission config data

    # interpreting engineering data
    tmp = parse_engr_time(engr_dict, fill_NaT=fill_NaT)
    if tmp: 
        out_dict["Timestamps"] = tmp

    # interpreting GPS and Iridium location data
    if "gps" in msg_dict:
        out_dict["GPS"] = parse_gps(
            msg_dict["gps"], fill_value=fill_value, fill_NaT=fill_NaT
        )
        if consume: del msg_dict["gps"]
    if "Iridium" in msg_dict:
        out_dict["Iridium"] = parse_iridium(
            msg_dict["Iridium"], fill_value=fill_value, fill_NaT=fill_NaT
        )
        if consume: del msg_dict["Iridium"]

    # interpret log data
    if log_dict:
        log_out = log_extractor(log_dict, fill_value=fill_value)
    else:
        log_out = {}
    
    # Interpreting science data
    OCR_submap = None if (OCR_map is None) else OCR_map.get(float_id, None)
    if "discrete_samples" in msg_dict:
        discrete = parse_discrete(
            msg_dict["discrete_samples"], OCR_map = OCR_submap, 
            fill_value=fill_value, logger=logger
        )
        if consume: del msg_dict["discrete_samples"]
    else:
        discrete = {}

    if "cont_samples" in msg_dict:
        continuous = parse_continuous(
            msg_dict["cont_samples"], sort="asc", 
            fill_value=fill_value, logger=logger
        )
        if consume: del msg_dict["cont_samples"]
    else:
        continuous = []

    if "ParkPt" in msg_dict:
        parked = parse_parked(
            msg_dict["ParkPt"], "ParkPt", 
            fill_value = fill_value, fill_NaT = fill_NaT,
            logger = logger
        )
        if consume: del msg_dict["ParkPt"]
    elif "ParkPtFlbb" in msg_dict:
        parked = parse_parked(
            msg_dict["ParkPtFlbb"], "ParkPtFlbb", 
            fill_value = fill_value, fill_NaT = fill_NaT,
            logger = logger
        )
        if consume: del msg_dict["ParkPtFlbb"]
    else:
        parked = {}

    # merge isus and discrete nitrate data
    if isus_dict is None:
        nitrate = None
    else:
        nitrate = align_nitrate(
            discrete["NO3"], isus_dict["science_data"], "asc", 
            fill_value = fill_value, fill_NaT = fill_NaT, logger = logger
        )

    # merge dura and discrete pH data
    if dura_dict is None:
        pH = None
    else:
        pH = align_pH(
            discrete["pH"], dura_dict["science_data"], "asc",
            fill_value = fill_value, fill_NaT = fill_NaT, logger = logger
        )

    # write out timestamp of fall, drift, and rise of float
    if "Rise" in log_out: 
        out_dict["Fall"] = log_out["Fall"]
    if "Traj" in parked:
        out_dict["Drift"] = parked["Traj"]
    if "Fall" in log_out:
        out_dict["Rise"] = log_out["Rise"]

    # write out piston adjustments
    if "Piston" in log_out:
        out_dict["Piston"] = log_out["Piston"]

    # Write out CTD data
    if "CTD" in discrete:
        out_dict["CTD_Discrete"] = discrete["CTD"]
    if continuous:
        out_dict["CTD_Binned"] = continuous
    if "CTD" in parked:
        out_dict["CTD_Drift"] = parked["CTD"]

    # Write out extra sensor data
    if "FLBB" in discrete:
        out_dict["ECO_Discrete"] = discrete["FLBB"]
    if "FLBB" in parked:
        out_dict["ECO_Drift"] = parked["FLBB"]
    if "Optode" in discrete:
        out_dict["DO_Discrete"] = discrete["Optode"]

    if pH is not None:
        out_dict["pH_Discrete"] = pH
    elif "pH" in discrete:
        out_dict["pH_Discrete"] = discrete["pH"]

    if "OCR" in discrete:
        out_dict["OCR_Discrete"] = discrete["OCR"]

    if nitrate is not None:
        out_dict["NITRATE_Discrete"] = nitrate
    elif "NO3" in discrete:
        out_dict["NITRATE_Discrete"] = discrete["NO3"]

    # interpret calibration data
    if "OptodeAirCal" in msg_dict:
        out_dict["optode_air_calibration"] = parse_OptodeAirCal(
            msg_dict["OptodeAirCal"],
            fill_value = fill_value, fill_NaT = fill_NaT
        )
        if consume: del msg_dict["OptodeAirCal"]

    # Write raw mission config and engineering data
    if config_dict:
        out_dict["ARGO_Mission"] = parse_mission_config(config_dict)
        if consume: del msg_dict["mission_config"]
    if any(engr_list):
        out_dict["Engineering_Data"] = parse_engineering_data(engr_list)
        if consume: del msg_dict["engineering_data"]

    # Write log data
    if log_dict is not None:
        out_dict["Log"] = log_dict.copy()
        if consume: log_dict.clear()

    # Write dura data
    if dura_dict is not None:
        out_dict["dura"] = dura_dict.copy()
        if consume: dura_dict.clear()

    # Write isus data
    if isus_dict is not None:
        out_dict["isus"] = isus_dict.copy()
        if consume: isus_dict.clear()

    return out_dict

    
#### script use utilities

def make_outfile_stem(name, AOML_map, nest=False, cycle=None, level=0):

    if isinstance(name, str):

        if "." in name:

            if cycle is None:
                name, cycle = name.split(".")
            else:
                name, _ = name.split(".")

        name = int(name)

    if isinstance(cycle, str):
        cycle = int(cycle)

    aoml = AOML_map[name]

    if nest:
        return f"{aoml:05}/{aoml:05}_{name:06}_L{level:01}_{cycle:04}"
    else:
        return f"{aoml:05}_{name:06}_L{level:01}_{cycle:04}"


#### Script mode

if __name__=="__main__":

    import argparse, pathlib, os, pickle, json
    import jsonschema

    default_map = "L0_maps.pkl"
    default_aoml = "AomlIdMap"
    default_wmo = "WmoIdMap"
    default_ocr = "OcrMap.csv"
    dura_type = "MSC3"

    def is_latter_newer(path1, path2):
        t1 = pathlib.Path(path1).stat().st_mtime
        t2 = pathlib.Path(path2).stat().st_mtime
        return t2 > t1


    def is_timestamp_newer(tstamp, path):
        t2 = pathlib.Path(path).stat().st_mtime
        if isinstance(tstamp, datetime):
            tstamp = tstamp.timestamp()
        return tstamp > t2


    def iter_subdirectories(root):

        root = pathlib.Path(root)

        for p in root.rglob("*"):
            if p.is_dir():
                yield p


    def derive_filenames(path):

        path = pathlib.Path(path)
        
        suffix = path.suffix
        if suffix and suffix[1:].isalpha():
            path = path.with_suffix("")

        float_id, cycle = path.name.split(".")

        log1 = path.with_name(path.name + ".log")
        log2 = path.with_name(f"{float_id}.{int(cycle) + 1:03d}.log")
        cp = path.with_name(path.name + ".cp")
        dura = path.with_name(path.name + ".dura")
        isus = path.with_name(path.name + ".isus")

        return (log1, log2, cp, dura, isus)


    def generate_json(
        msg_path, aux, partial_log=False,
        out_root=".", nest=False, update=False,
        validator=None,
        logger=print
    ):

        AOML_map = aux["aoml"]
        WMO_map = aux["wmo"]
        OCR_map = aux["ocr"]

        msg = pathlib.Path(msg_path)
        stem = msg.with_suffix("")

        logger(f"Processing {stem}...")

        out_name = make_outfile_stem(stem.name, AOML_map, nest=nest)
        out_path = pathlib.Path(out_root).joinpath(out_name + ".json")

        log1, log2, cp, dura, isus = derive_filenames(msg_path)

        out_flag = out_path.is_file()
        log1_flag = log1.is_file()
        log2_flag = log2.is_file()
        cp_flag = cp.is_file()
        dura_flag = dura.is_file()
        isus_flag = isus.is_file()

        out_t = out_path.stat().st_mtime if out_flag else 0
        msg_t = msg.stat().st_mtime
        log1_t = log1.stat().st_mtime if log1_flag else 0
        log2_t = log2.stat().st_mtime if log2_flag else 0
        cp_t = cp.stat().st_mtime if cp_flag else 0
        dura_t = dura.stat().st_mtime if dura_flag else 0
        isus_t = isus.stat().st_mtime if isus_flag else 0

        if update and out_t > max(msg_t, log1_t, log2_t, cp_t, dura_t, isus_t):
            logger("Nothing to do. Bail.")
            return None

        msg_dict = msg_tokenizer(
            msg, logger=lambda x: logger("[MSG] " + x)
        )

        if log1_flag:
            if log2_flag:
                log1_list, cuts1 = log_tokenizer(
                    log1, fill_value=-999,
                    logger=lambda x: logger("[LOG] " + x)
                )
                log2_list, cuts2 = log_tokenizer(
                    log2, fill_value=-999,
                    logger=lambda x: logger("[LOG] " + x)
                )
                log_list = log1_list[cuts1[0]:] + log2_list[:cuts2[0]]
            elif partial_log:
                log_list, cuts1 = log_tokenizer(
                    log1, fill_value=-999,
                    logger=lambda x: logger("[LOG] " + x)
                )
            else:
                logger("Incomplete log. Bail.")
                return None
        else:
            log_list = None

        if cp_flag:
            cp_dict = None
        else:
            cp_dict = None

        if dura_flag:
            dura_dict = dura_tokenizer(
                dura, dura_type,
                fill_value=-999,
                logger=lambda x: logger("[DURA] " + x)
            )
        else:
            dura_dict = None

        if isus_flag:
            isus_dict = isus_tokenizer(
                isus,
                fill_value=-999,
                logger=lambda x: logger("[ISUS] " + x)
            )
        else:
            isus_dict = None

        out = L0_parser(
            msg_dict, log_list, dura_dict, isus_dict, cp_dict, 
            AOML_map, WMO_map, OCR_map,
            supp_dict=None, consume=False, 
            fill_value=None, fill_NaT=None, logger=print
        )

        if validator is not None:
            try:
                jsonschema.validate(out, validator)
            except jsonschema.exceptions.ValidationError as e:
                logger(f"Schema validation failed: {e.message}. Bail.")
                return None

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as outfile:
            logger(f"Writing output to {out_path}")
            json.dump(out, outfile, indent=2)

        return None


    def write_mapping(aoml, wmo, ocr, out, update=False, format="pickle", logger=print):

        aoml_p = pathlib.Path(aoml)
        wmo_p = pathlib.Path(wmo)
        ocr_p = pathlib.Path(ocr)
        out_p = pathlib.Path(out)

        if update and pathlib.Path(out).is_file():

            aoml_t = aoml_p.stat().st_mtime if aoml_p.is_file() else 0
            wmo_t = wmo_p.stat().st_mtime if wmo_p.is_file() else 0
            ocr_t = ocr_p.stat().st_mtime if ocr_p.is_file() else 0
            out_t = out_p.stat().st_mtime

            if (out_t > ocr_t) and (out_t > aoml_t) and (out_t > wmo_t):
                logger("Nothing to do. Exit.")
                return # nothing to do

            if out_p.suffix == ".json":
                with open(out, "r") as infile:
                    data = json.load(infile)
            else:
                with open(out, "rb") as infile:
                    data = pickle.load(infile)

            if (out_t < ocr_t):
                logger("Parsing OCR file...")
                data["ocr"] = parse_OCR_map(ocr_p)
            if (out_t < aoml_t):
                logger("Parsing AOML ID file...")
                data["aoml"] = parse_AOML_ID_map(aoml_p, logger=logger)
            if (out_t < wmo_t):
                logger("Parsing WMO ID file...")
                data["wmo"] = parse_WMO_ID_map(wmo_p, logger=logger)

        else:
            data = {}
            
            logger("Parsing OCR file...")
            data["ocr"] = parse_OCR_map(ocr_p)

            logger("Parsing AOML ID file...")
            data["aoml"] = parse_AOML_ID_map(aoml_p, logger=logger)

            logger("Parsing WMO ID file...")
            data["wmo"] = parse_WMO_ID_map(wmo_p, logger=logger)

        if out_p.suffix == ".json":
            logger(f"Writing output to {out_p}")
            with open(out_p, "w") as outfile:
                json.dump(data, outfile, indent=2)
        else:
            logger(f"Writing output to {out_p}")
            with open(out_p, "wb") as outfile:
                pickle.dump(data, outfile)

    # create parser; delegate to sub-parsers
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    # build-aux command
    p_build = subparsers.add_parser("build")
    p_build.add_argument("-u", "--update", action="store_true")
    p_build.add_argument("--aoml", default=default_aoml)
    p_build.add_argument("--wmo", default=default_wmo)
    p_build.add_argument("--ocr", default=default_ocr)
    p_build.add_argument("-d", "--in_dir", default=".")
    p_build.add_argument("-o", "--output", default=default_map)

    # convert command
    p_conv = subparsers.add_parser("convert")
    p_conv.add_argument("-m", "--mapping", default=default_map)
    p_conv.add_argument("-s", "--schema", default=None)
    p_conv.add_argument("-u", "--update", action="store_true")
    p_conv.add_argument("-r", "--recursive", action="store_true")
    p_conv.add_argument("-n", "--nest_output", action="store_true")
    p_conv.add_argument("-p", "--partial_log", action="store_true")
    p_conv.add_argument("-i", "--input", default="*.*")
    p_conv.add_argument("-d", "--in_dir", default=".")
    p_conv.add_argument("-o", "--out_dir", default=".")

    # validate command
    p_valid = subparsers.add_parser("validate")
    p_valid.add_argument("-s", "--schema", default="UW_schema_L0.json")
    p_valid.add_argument("-r", "--recursive", action="store_true")
    p_valid.add_argument("-i", "--input", default="*.json")
    p_valid.add_argument("-d", "--in_dir", default=".")

    # parse input arguments
    args = parser.parse_args()

    # build auxiliary data file
    if args.command == "build":

        root = pathlib.Path(args.in_dir)

        aoml = root.joinpath(args.aoml)
        wmo = root.joinpath(args.wmo)
        ocr = root.joinpath(args.ocr)
        out = pathlib.Path(args.output)

        write_mapping(aoml, wmo, ocr, out, update=args.update)

    # perform conversion to json
    elif args.command == "convert":

        # load auxiliary map
        map_path = pathlib.Path(args.mapping)
        if map_path.suffix == ".json":
            with open(map_path, "r") as infile:
                aux = json.load(infile)
        else:
            with open(map_path, "rb") as infile:
                aux = pickle.load(infile)

        if args.schema is not None:
            with open(args.schema, "r") as infile:
                validator = json.load(infile)
        else:
            validator = None

        in_glob = args.input + ".msg"

        root = pathlib.Path(args.in_dir)

        if args.recursive:
            targets = []
            for _p in iter_subdirectories(root):
                targets = itertools.chain(targets, _p.glob(in_glob))
        else:
            targets = root.glob(in_glob)

        for _x in targets:
            generate_json(
                _x, aux, 
                partial_log=args.partial_log,
                out_root=args.out_dir, 
                nest=args.nest_output, 
                update=args.update,
                validator=validator
            )

    # validate output json
    elif args.command == "validate":

        with open(args.schema, "r") as infile:
            validator = json.load(infile)

        root = pathlib.Path(args.in_dir)

        if args.recursive:
            targets = []
            for _p in iter_subdirectories(root):
                targets = itertools.chain(targets, _p.glob(args.input))
        else:
            targets = root.glob(args.input)

        for _x in targets:

            print(f"Validating {_x}...")

            with open(_x, "r") as infile:
                _j = json.load(infile)

            try:
                jsonschema.validate(_j, validator)
            except jsonschema.exceptions.ValidationError as e:
                print(f"[WARNING] Validation failed: {e.message}.")
            else:
                print("Validation succeeded.")