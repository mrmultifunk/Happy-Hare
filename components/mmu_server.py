# Happy Hare MMU Software
# Moonraker support for a file-preprocessor that injects MMU metadata into gcode files
#
# Copyright (C) 2023  Kieran Eglin <@kierantheman (discord)>, <kieran.eglin@gmail.com>
#
# Spoolman integration, colors & temp extension
# Copyright (C) 2023  moggieuk#6538 (discord) moggieuk@hotmail.com
#
# (\_/)
# ( *,*)
# (")_(") MMU Ready
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#

import logging, os, sys, re, time
import runpy, argparse, shutil, traceback, tempfile, filecmp

class MmuServer:
    def __init__(self, config):
        self.config = config
        self.server = config.get_server()

        # Spoolman filament info retrieval functionality and update reporting
        self.server.register_remote_method("spoolman_get_filaments", self.get_filaments)

        self.setup_placeholder_processor(config) # Replaces file_manager/metadata with this file

    # Logic to provide spoolman integration.
    # Leverage configuration from Spoolman component
    async def get_filaments(self, gate_ids):
        spoolman = self.server.lookup_component("spoolman")
        kapis = self.server.lookup_component("klippy_apis")

        gate_dict = {}
        for gate_id, spool_id in gate_ids:
            full_url = f"{spoolman.spoolman_url}/v1/spool/{spool_id}"

            response = await spoolman.http_client.request(method="GET", url=full_url, body=None)
            if not response.has_error():

                record = response.json()
                filament = record["filament"]

                material = filament.get('material', '')[:6] # Keep material spec short for Klipperscreen
                color_hex = filament.get('color_hex', '')[:6] # Strip alpha channel if it exists

                gate_dict[gate_id] = {'spool_id': spool_id, 'material': material, 'color': color_hex}
            elif response.status_code != 404:
                response.raise_for_status()
        try:
            await kapis.run_gcode(f"MMU_GATE_MAP MAP=\"{gate_dict}\" QUIET=1")
        except self.server.error as e:
            logging.info(f"mmu_server: Exception running MMU gcode: %s" % str(e))

        return gate_dict

    def setup_placeholder_processor(self, config):
        # Switch out the metadata processor with this module with handles placeholders
        args = " -m" if config.getboolean("enable_file_preprocessor", True) else ""
        args += " -n" if config.getboolean("enable_toolchange_next_pos", True) else ""
        from .file_manager import file_manager
        file_manager.METADATA_SCRIPT = os.path.abspath(__file__) + args

def load_component(config):
    return MmuServer(config)



#
# Beyond this point this module acts like an extended file_manager/metadata module
#

MMU_REGEX = r"^; processed by HappyHare"
SLICER_REGEX = r"^;.*generated by ([a-z]*) .*$"

TOOL_DISCOVERY_REGEX = r"((^MMU_CHANGE_TOOL(_STANDALONE)? .*?TOOL=)|(^T))(?P<tool>\d{1,2})"
METADATA_TOOL_DISCOVERY = "!referenced_tools!"

# PS/SS uses "extruder_colour", Orca uses "filament_colour" but extruder_colour can exist with empty or single color
COLORS_REGEX = r"^; (?:extruder_colour|filament_colour) = (#.*;.*)$"
METADATA_COLORS = "!colors!"

TEMPS_REGEX = r"^; (nozzle_)?temperature =(.*)$" # Orca Slicer has the 'nozzle_' prefix, others might not
METADATA_TEMPS = "!temperatures!"

MATERIALS_REGEX = r"^; filament_type =(.*)$"
METADATA_MATERIALS = "!materials!"

PURGE_VOLUMES_REGEX = r"^; (flush_volumes_matrix|wiping_volumes_matrix) =(.*)$" # flush.. in Orca, wiping... in PS
METADATA_PURGE_VOLUMES = "!purge_volumes!"

# Detection for next pos processing
T_PATTERN  = r'^T(\d+)$'
G1_PATTERN = r'^G[01](?:\s+X([\d.]*)|\s+Y([\d.]*))+.*$'

def gcode_processed_already(file_path):
    """Expects first line of gcode to be '; processed by HappyHare'"""

    mmu_regex = re.compile(MMU_REGEX, re.IGNORECASE)

    with open(file_path, 'r') as in_file:
        line = in_file.readline()
        return mmu_regex.match(line)

def parse_gcode_file(file_path):
    slicer_regex = re.compile(SLICER_REGEX, re.IGNORECASE)
    tools_regex = re.compile(TOOL_DISCOVERY_REGEX, re.IGNORECASE)
    colors_regex = re.compile(COLORS_REGEX, re.IGNORECASE)
    temps_regex = re.compile(TEMPS_REGEX, re.IGNORECASE)
    materials_regex = re.compile(MATERIALS_REGEX, re.IGNORECASE)
    purge_volumes_regex = re.compile(PURGE_VOLUMES_REGEX, re.IGNORECASE)

    has_tools_placeholder = has_colors_placeholder = has_temps_placeholder = has_materials_placeholder = has_purge_volumes_placeholder = False
    found_colors = found_temps = found_materials = found_purge_volumes = False
    slicer = None

    tools_used = set()
    colors = []
    temps = []
    materials = []
    purge_volumes = []

    with open(file_path, 'r') as in_file:
        for line in in_file:
            # Discover slicer
            if not slicer and line.startswith(";"):
                match = slicer_regex.match(line)
                if match:
                    slicer = match.group(1).lower()
            # !referenced_tools! processing
            if not has_tools_placeholder and METADATA_TOOL_DISCOVERY in line:
                has_tools_placeholder = True

            match = tools_regex.match(line)
            if match:
                tool = match.group("tool")
                tools_used.add(int(tool))

            # !colors! processing
            if not has_colors_placeholder and METADATA_COLORS in line:
                has_colors_placeholder = True

            if not found_colors:
                match = colors_regex.match(line)
                if match:
                    colors_csv = [color.strip().lstrip('#') for color in match.group(1).split(';')]
                    colors.extend(colors_csv)
                    found_colors = all(len(c) > 0 for c in colors)

            # !temperatures! processing
            if not has_temps_placeholder and METADATA_TEMPS in line:
                has_temps_placeholder = True

            if not found_temps:
                match = temps_regex.match(line)
                if match:
                    temps_csv = re.split(';|,', match.group(2).strip())
                    temps.extend(temps_csv)
                    found_temps = True

            # !materials! processing
            if not has_materials_placeholder and METADATA_MATERIALS in line:
                has_materials_placeholder = True

            if not found_materials:
                match = materials_regex.match(line)
                if match:
                    materials_csv = match.group(1).strip().split(';')
                    materials.extend(materials_csv)
                    found_materials = True
            
            # !purge_volumes! processing
            if not has_purge_volumes_placeholder and METADATA_PURGE_VOLUMES in line:
                has_purge_volumes_placeholder = True
            
            if not found_purge_volumes:
                match = purge_volumes_regex.match(line)
                if match:
                    purge_volumes_csv = match.group(2).strip().split(',')
                    purge_volumes.extend(purge_volumes_csv)
                    found_purge_volumes = True

    return (has_tools_placeholder or has_colors_placeholder or has_temps_placeholder or has_materials_placeholder or has_purge_volumes_placeholder,
            sorted(tools_used), colors, temps, materials, purge_volumes, slicer)

def process_file(input_filename, output_filename, insert_nextpos, tools_used, colors, temps, materials, purge_volumes):

    t_pattern = re.compile(T_PATTERN)
    g1_pattern = re.compile(G1_PATTERN)

    with open(input_filename, 'r') as infile, open(output_filename, 'w') as outfile:
        buffer = [] # Buffer lines between a "T" line and the next matching "G1" line
        tool = None # Store the tool number from a "T" line
        outfile.write('; processed by HappyHare\n')

        for line in infile:
            line = add_placeholder(line, tools_used, colors, temps, materials, purge_volumes)
            if tool is not None:
                # Buffer subsequent lines after a "T" line until next "G1" x,y move line is found
                buffer.append(line)
                g1_match = g1_pattern.match(line)
                if g1_match:
                    # Now replace "T" line and write buffered lines, including the current "G1" line
                    if insert_nextpos:
                        x, y = g1_match.groups()
                        outfile.write(f'MMU_CHANGE_TOOL TOOL={tool} NEXT_POS="{x},{y}" ; T{tool}\n')
                    else:
                        outfile.write(f'MMU_CHANGE_TOOL TOOL={tool} ; T{tool}\n')
                    for buffered_line in buffer:
                        outfile.write(buffered_line)
                    buffer.clear()
                    tool = None
                continue

            t_match = t_pattern.match(line)
            if t_match:
                tool = t_match.group(1)
            else:
                outfile.write(line)

        # If there is anything left in buffer it means there wasn't a final "G1" line
        if buffer:
            outfile.write(f"T{tool}\n")
            outfile.write(f'MMU_CHANGE_TOOL TOOL={tool} ; T{tool}\n')
            for line in buffer:
                outfile.write(line)

def add_placeholder(line, tools_used, colors, temps, materials, purge_volumes):
    # Ignore comment lines to preserve slicer metadata comments
    if not line.startswith(";"):
        if METADATA_TOOL_DISCOVERY in line:
            line = line.replace(METADATA_TOOL_DISCOVERY, ",".join(map(str, tools_used)))
        if METADATA_COLORS in line:
            line = line.replace(METADATA_COLORS, ",".join(map(str, colors)))
        if METADATA_TEMPS in line:
            line = line.replace(METADATA_TEMPS, ",".join(map(str, temps)))
        if METADATA_MATERIALS in line:
            line = line.replace(METADATA_MATERIALS, ",".join(map(str, materials)))
        if METADATA_PURGE_VOLUMES in line:
            line = line.replace(METADATA_PURGE_VOLUMES, ",".join(map(str, purge_volumes)))
    return line

def main(path, filename, insert_placeholders=False, insert_nextpos=False):
    file_path = os.path.join(path, filename)
    if not os.path.isfile(file_path):
        metadata.logger.info(f"File Not Found: {file_path}")
        sys.exit(-1)
    try:
        metadata.logger.info(f"mmu_server: Pre-processing file: {file_path}")
        fname = os.path.basename(file_path)
        if fname.endswith(".gcode") and not gcode_processed_already(file_path):
            with tempfile.TemporaryDirectory() as tmp_dir_name:
                tmp_file = os.path.join(tmp_dir_name, fname)

                if insert_placeholders:
                    start = time.time()
                    has_placeholder, tools_used, colors, temps, materials, purge_volumes, slicer = parse_gcode_file(file_path)
                    metadata.logger.info("Reading placeholders took %.2fs. Detected gcode by slicer: %s" % (time.time() - start, slicer))
                else:
                    tools_used = colors = temps = materials = purge_volumes = slicer = None
                    has_placeholder = False

                if (insert_nextpos and len(tools_used) > 0) or has_placeholder:
                    start = time.time()
                    msg = []
                    if has_placeholder:
                        msg.append("Writing MMU placeholders")
                    if insert_nextpos:
                        msg.append("Inserting next position to tool changes")
                    process_file(file_path, tmp_file, insert_nextpos, tools_used, colors, temps, materials, purge_volumes)
                    metadata.logger.info("mmu_server: %s took %.2fs" % (",".join(msg), time.time() - start))

                    # Move temporary file back in place
                    if os.path.islink(file_path):
                        file_path = os.path.realpath(file_path)
                    if not filecmp.cmp(tmp_file, file_path):
                        shutil.move(tmp_file, file_path)
                    else:
                        metadata.logger.info(f"Files are the same, skipping replacement of: {file_path} by {tmp_file}")
                else:
                    metadata.logger.info(f"No MMU metadata placeholders found in file: {file_path}")

    except Exception:
        metadata.logger.info(traceback.format_exc())
        sys.exit(-1)

# When run separately this module wraps metadata to extend pre-processing functionality
if __name__ == "__main__":
    # Make it look like we are running in the file_manager directory
    directory = os.path.dirname(os.path.abspath(__file__))
    target_dir = directory + "/file_manager"
    os.chdir(target_dir)
    sys.path.insert(0, target_dir)

    import metadata
    metadata.logger.info(f"mmu_server: Running MMU enhanced version of metadata")

    # We need to re-parse arguments anyway, so this way, whilst relaxing need to copy code, isn't useful
    #runpy.run_module('metadata', run_name="__main__", alter_sys=True)

    # Parse start arguments (copied from metadata.py)
    parser = argparse.ArgumentParser(description="GCode Metadata Extraction Utility")
    parser.add_argument("-f", "--filename", metavar='<filename>', help="name gcode file to parse")
    parser.add_argument("-p", "--path", default=os.path.abspath(os.path.dirname(__file__)), metavar='<path>', help="optional absolute path for file")
    parser.add_argument("-u", "--ufp", metavar="<ufp file>", default=None, help="optional path of ufp file to extract")
    parser.add_argument("-o", "--check-objects", dest='check_objects', action='store_true', help="process gcode file for exclude opbject functionality")
    parser.add_argument("-m", "--placeholders", dest='placeholders', action='store_true', help="process happy hare mmu placeholders")
    parser.add_argument("-n", "--nextpos", dest='nextpos', action='store_true', help="add next position to tool change")
    args = parser.parse_args()
    check_objects = args.check_objects
    enabled_msg = "enabled" if check_objects else "disabled"
    metadata.logger.info(f"Object Processing is {enabled_msg}")

    # Original metadata parser
    metadata.main(args.path, args.filename, args.ufp, check_objects)

    # Second parsing for mmu placeholders and next pos insertion
    main(args.path, args.filename, args.placeholders, args.nextpos)
