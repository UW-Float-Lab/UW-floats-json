'''
Version: 0.2.0
'''

import re, itertools
from datetime import datetime, UTC

#### Default configurations

# default supplemental information for output json
default_supp = {
  "DECODER_VERSION": "0.2.0",
  "SCHEMA_VERSION": "0.2.0",
  "PI": "RISER, STEVE AND GRAY, ALISON",
  "OPERATING_INSTITUTION": "UW, Seattle, WA",
  "FILE_CREATION_INSTITUTION": "UW, Seattle, WA",
  "PROJECT_NAME": "Core Float"
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

# regex for engineering parameters
engr_rx = re.compile(r"^([A-Za-z0-9]+)=(.*?)$")

# regex for element of array engineering parameters
engr_array_rx = re.compile(r"^([A-Za-z0-9]+)\[([0-9]+)\]=(.*?)$")

# regex for a generic log entry
log_rx = re.compile(r"^\((" + mmmdy_hms + r"),\s+([0-9]+)\s+sec\)\s+([_:A-Za-z0-9]+)(?:\(\))?\s+(.*?)$")

# regex for parsing datetime values in engineering datetime information
engr_time_rx = re.compile(r"([0-9]+)\s+(" + mmmdy_hms + ")")


#### Utility functions

def parseHex(val):
    '''
    Parse a hexadecimal string into integer
    '''
    return int(val, 16)


def parseInt(val):
    '''
    Parse an integer string into integer. nan is converted to None
    '''
    return None if (val.strip().lower() == "nan") else int(val)


def parseFloat(val):
    '''
    Parse a floating-point number string into float. nan is converted to None
    '''
    return None if (val.strip().lower() == "nan") else float(val)


def parseDimFloat(val):
    '''
    Parse a string containing a floating-point value followed by unit into 
    a tuple (number, unit). If nan is encountered None is returned for 
    both number and unit. If the string does not take the expected pattern
    a ValueError is raised
    '''
    
    if val.strip().lower() == "nan": 
        return (None, None)
    if (rx_match := dim_num_rx.match(val)):
        return (float(rx_match[1]), rx_match[2])
    else:
        raise ValueError("Input string does not conform to the expected pattern")


def parseDimInt(val):
    '''
    Parse a string containing an integer value followed by unit into a tuple
    (number, unit). If nan is encountered None is returned for both. If the 
    string does not conform to the expected pattern a ValueError is raised.
    '''
    if val.strip() == "nan": 
        return (None, None)
    if (rx_match := dim_num_rx.match(val)):
        return (int(rx_match[1]), rx_match[2])
    else:
        raise ValueError("Input string does not conform to the expected pattern")


def decode_hex(code, jump = 0x10000, cut = 0x8000, scalar = 1, offset = 0, dp = 0):
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
        return None

    # negative values
    elif val > cut:
        val -= jump

    return round(scalar * val + offset, dp)
    
    
def decode_time(value):
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
            
    return value.isoformat() + "Z"


def dict_to_list(in_dict):
    l = max(in_dict.keys())
    out = [None] * (l + 1)
    for k, v in in_dict.items():
        out[k] = v
    return out


#### Componenet functions (for decoding specific part(s) of file/python object)

def infer_instrument(msg_dict):
    '''
    Infer the float type
    '''
    # to be developed
    return "UW-APEX"


def infer_positioning(msg_dict):
    '''
    Infer the mechanism for positioning the float
    '''
    
    if "gps" in msg_dict and msg_dict["gps"]:
        return "GPS"
    elif "Iridium" in msg_dict and msg_dict["iridium"]:
        return "Iridium"
    else:
        return None


def parse_gps(gps_list):
    '''
    Parse GPS information
    '''
    out = []

    for entry in gps_list:
        out_entry = {}
        out_entry["description"] = "GPS_FIX"
        out_entry["TIME"] = decode_time(entry["time"])
        out_entry["LATITUDE"] = parseFloat(entry["lat"])
        out_entry["LONGITUDE"] = parseFloat(entry["lon"])
        out_entry["sat_cnt"] = parseInt(entry["nsat"])
        out_entry["time_to_fix"] = parseInt(entry["t_fix"])
        out.append(out_entry)
        
    return out


def parse_iridium(irid_list):
    '''
    Parse Iridium information
    '''
    out = []

    for entry in irid_list:
        out_entry = {}
        out_entry["LATITUDE"] = parseFloat(entry["lat"])
        out_entry["LONGITUDE"] = parseFloat(entry["lon"])
        out_entry["TIME"] = decode_time(entry["time"])
        out_entry["x"], unit = parseDimFloat(entry["x"])
        assert unit == "km"
        out_entry["y"], unit = parseDimFloat(entry["y"])
        assert unit == "km"
        out_entry["z"], unit = parseDimFloat(entry["z"])
        assert unit == "km"
        out_entry["system_time"] = parseHex(entry["sys_time"])
        out.append(out_entry)

    return out


def parse_engr_time(time_dict):
    '''
    Parse timestamp information in engineering data
    '''
    
    out = {}
    
    rx_match = engr_time_rx.match(time_dict.get('TimeStartDescent', ""))
    if rx_match: 
        out["StartDescent"] = decode_time(rx_match[2])

    rx_match = engr_time_rx.match(time_dict.get('TimeStartPark', ""))
    if rx_match: 
        out["StartPark"] = decode_time(rx_match[2])

    rx_match = engr_time_rx.match(time_dict.get('TimeStartProfileDescent', ""))
    if rx_match: 
        out["StartProfileDescent"] = decode_time(rx_match[2])

    rx_match = engr_time_rx.match(time_dict.get('TimeStartProfile', ""))
    if rx_match: 
        out["StartProfile"] = decode_time(rx_match[2])

    rx_match = engr_time_rx.match(time_dict.get('TimeStopProfile', ""))
    if rx_match: 
        out["StopProfile"] = decode_time(rx_match[2])

    rx_match = engr_time_rx.match(time_dict.get('TimeStartTelemetry', ""))
    if rx_match: 
        out["StartTelemetry"] = decode_time(rx_match[2])
    
    return out


def parse_discrete(disc_dict):
    '''
    Parse discrete CTD samples of the float
    '''
    out = []
    
    if len(disc_dict["headers"]) == 3:
        for item in disc_dict["park_data"]:
            out.append({"PRES": parseFloat(item["p"]), "TEMP": parseFloat(item["t"]), "PSAL": parseFloat(item["s"])})
        for item in disc_dict["data"]:
            out.append({"PRES": parseFloat(item["p"]), "TEMP": parseFloat(item["t"]), "PSAL": parseFloat(item["s"])})

    return out


def parse_continuous(cont_dict):
    '''
    Parse continuous CTD samples of the float
    '''

    out = []

    if cont_dict["hex_len"] == 14:
        
        for item in cont_dict["data"]:
            
            if item == "0" * 14: continue

            tmp = {}
            tmp["PRES"] = decode_hex(item[:4], cut = 0xf000, scalar = 0.1, dp = 1)
            tmp["TEMP"] = decode_hex(item[4:8], cut = 0xf000, scalar = 0.001, dp = 3)
            tmp["PSAL"] = decode_hex(item[8:12], cut = 0xf000, scalar = 0.001, dp = 3)
            tmp["n_samp"] = decode_hex(item[12:])

            out.append(tmp)
    
    return out


def parse_parked(park_dict, type):
    '''
    Parse parked CTD samples of the float
    '''
    out = []
    
    if type == "ParkPt":

        for item in park_dict:
            tmp = {}
            tmp["PRES"] = float(item["p"])
            tmp["TEMP"] = float(item["t"])
            tmp["TIME"] = decode_time(item["time"])
            out.append(tmp)

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


#### conglomerate functions

def msg_tokenizer(file, logger=print):
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
    with open(file + ".msg", "r") as infile:
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
                    if "iridium" not in out:
                        out["iridium"] = []
                    out["iridium"].append(iridium_sect)
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
                    out["profile_terminated"] = {"FloatId": rx_match[1], "ProfileID": rx_match[2], "time": rx_match[3]}
                    
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
                        
                    continuous = {"SerNo": rx_match[1], "NSample": rx_match[2], "NBin": rx_match[3]}
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
                        logger('Duplicated key: "iridium"')
                    iridium_sect |= geo
    
                elif (rx_match := irid_fix_rx.match(line)):
                    fix = {"lon": rx_match[1], "lat": rx_match[2], "epoch": rx_match[3], "time": rx_match[4]}
                    if {"lon", "lat", "time", "epoch"} & iridium_sect.keys():
                        logger('Duplicated key: "iridium"')
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
            if "iridium" not in out:
                out["iridium"] = []
            out["iridium"].append(iridium_sect)
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


def log_tokenizer(file, logger=print):
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
    with open(file + ".log", "r") as infile:
        lines = infile.readlines()
    
    for line in lines:

        if (rx_match := log_rx.match(line)):
            
            cur_mtime = parseInt(rx_match[2])
            entry = {
                "time": decode_time(rx_match[1]), 
                "mission_time": cur_mtime, 
                "call": rx_match[3], 
                "message": rx_match[4]
            }
            
            if cur_mtime < prev_mtime:
                cuts.append(len(out))
            prev_mtime = cur_mtime
            
            out.append(entry)

        elif line.strip() == "" or line.strip() == "<EOT>":
            pass

        else:
            logger('Not decoded: "' + line + '"')

    return (out, cuts)


def L0_parser(msg_dict, log_dict, supp_dict=None, consume=False, logger=print):
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
    out_dict["FILE_CREATION_DATE"] = t_string
    out_dict["FILE_UPDATE_DATE"] = t_string
    out_dict["DECODER_VERSION"] = supp_dict["DECODER_VERSION"]
    out_dict["SCHEMA_VERSION"] = supp_dict["SCHEMA_VERSION"]
    out_dict["INTERNAL_ID_NUMBER"] = int(engr_dict["FloatId"])
    out_dict["TRANSMISSION ID NUMBER"] = None
    out_dict["INSTRUMENT_TYPE"] = infer_instrument(msg_dict)
    out_dict["WMO_ID NUMBER"] = None # to be filled in
    out_dict["WMO INSTRUMENT TYPE (TABLE 1770)"] = None # to be filled in
    out_dict["WMO RECORDER TYPE (TABLE 4770)"] = None # to be filled in
    out_dict["OPERATING_INSTITUTION"] = supp_dict["OPERATING_INSTITUTION"]
    out_dict["FILE_CREATION_INSTITUTION"] = supp_dict["FILE_CREATION_INSTITUTION"]
    out_dict["PI"] = supp_dict["PI"]
    out_dict["PROJECT_NAME"] = supp_dict["PROJECT_NAME"]
    out_dict["PROFILE_NUMBER"] = int(engr_dict["ProfileId"], 10)
    out_dict["POSITIONING_SYSTEM"] = infer_positioning(msg_dict)

    # interpreting mission config data

    # interpreting engineering data
    tmp = parse_engr_time(engr_dict)
    if tmp: 
        out_dict["Timestamps"] = tmp

    if "gps" in msg_dict:
        out_dict["GPS"] = parse_gps(msg_dict["gps"])
        if consume: del msg_dict["gps"]
    if "iridium" in msg_dict:
        out_dict["Iridium"] = parse_iridium(msg_dict["iridium"])
        if consume: del msg_dict["iridium"]
    if "discrete_samples" in msg_dict:
        out_dict["CTD Discrete"] = parse_discrete(msg_dict["discrete_samples"])
        if consume: del msg_dict["discrete_samples"]
    if "cont_samples" in msg_dict:
        out_dict["CTD Binned"] = parse_continuous(msg_dict["cont_samples"])
        if consume: del msg_dict["cont_samples"]
    if "ParkPt" in msg_dict:
        out_dict["CTD Drift"] = parse_parked(msg_dict["ParkPt"], "ParkPt")
        if consume: del msg_dict["ParkPt"]
    if config_dict:
        out_dict["raw_mission_config"] = parse_mission_config(config_dict)
    if any(engr_list):
        out_dict["raw_engineering_data"] = parse_engineering_data(engr_list)
    if log_dict is not None:
        out_dict["Log"] = log_dict.copy()
        if consume: log_dict.clear()
    
    return out_dict