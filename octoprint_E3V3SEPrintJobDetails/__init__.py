# Coding=utf 8
from __future__ import absolute_import
import re
import time
import octoprint.plugin


class E3v3seprintjobdetailsPlugin(octoprint.plugin.StartupPlugin,
                                  octoprint.plugin.EventHandlerPlugin,
                                  octoprint.plugin.ProgressPlugin,
                                  octoprint.plugin.SettingsPlugin,
                                  octoprint.plugin.TemplatePlugin
                                  ):
    
        def __init__(self): # init global vars
            self.was_loaded = False
            self.print_time_known = False
            self.total_layers_known = False
            self.prev_print_time_left = None
            self.prev_layer_number = None
            self.await_start = False
            self.await_metadata = False
            self.printing_job = False
            self.counter = 0
            self.start_time = None
            self.elapsed_time = None
            self.layer_number = 0
            self.send_m73 = False
            self.file_name = None
            self.file_path = None
            self.print_time = None
            self.print_time_left = None
            self.current_layer = None
            self.progress = None
            self.total_layers = 0
            self.myETA = None
            self.total_layers_found = None

        def get_settings_defaults(self):
            return dict(
                enable_o9000_commands=False,  # Default value for the slider.
                 progress_type="time_progress"  # Default option selected for radio buttons.
            )

        def get_template_configs(self): # get the values
            return [
                dict(type="settings", template="settings.e3v3seprintjobdetails_plugin_settings.jinja2", name="E3V3SE Print Job Details", custom_bindings=False)
            ]

        def on_after_startup(self):
            self._logger.info(">>>>>> E3v3seprintjobdetailsPlugin Loaded <<<<<<")
            self.slicer_values()

        def slicer_values(self):
            self._logger.info(f"Plugin Version: {self._plugin_version}")
            self._logger.info(f"Sliders values:")
            self._logger.info(f"Enable O9000 Commands: {self._settings.get(['enable_o9000_commands'])}")
            self._logger.info(f"Progress based on: {self._settings.get(['progress_type'])}")

        def on_event(self, event, payload):
            self._logger.info(f">>>>>> E3v3seprintjobdetailsPlugin Event detected: {event}")  # Verify Events, Better to comment this

            if event == "Connected":
                self.send_O9000_cmd("OCON|")

            if event == "PrintCancelled":  # clean variables after cancellation
                self.cleanup()

            if event == "FileSelected":  # If file selected gather all data
                self.was_loaded = True
                time.sleep(0.3)
                self.await_start = True  # Lets Wait to complete
                self._logger.info(">>>>>> Loaded File, Waiting for PrintStarted")

            if event == "PrintStarted":
                self.slicer_values()
                self.start_time = time.time() # save the mark of the start
                if self.await_start and self.was_loaded:  # Are we waiting...
                    self._logger.info(f">>>+++ PrintStarted with Loaded File waiting for metadata")
                    self.await_metadata = True
                    time.sleep(.3)
                    self.get_print_info(payload)

                    if self._settings.get(["progress_type"]) == "m73_progress":
                        self._logger.info(f">>>+++ PrintStarted with M73 command enabled")
                        #self.send_m73 = True

                if not self.was_loaded: # Direct print from GUI?
                    self._logger.info(">>>+++ PrintedStarted but File Not Loaded, wait for metadata")
                    self.await_metadata = True

            if event == "MetadataAnalysisFinished":
                if self.await_metadata: # Metadata finished and we have a flag from the flow of Load -> Print -> Read -> Start
                    self._logger.info(">>>+++ PrintedStarted and Metadata Finish, get print Info")
                    time.sleep(.3)
                    self.printing_job = True
                    self.get_print_info(payload)

            if event == "ZChange":  # Update the info every Z change
                # If the flow was a direct print from GUI: Print-> Start, and the file was already analized we will not have metadata step
                # So this is our insurance for a direct print of old file, a second print of existing analized file we will want to update all.
                # Check if the printer is printing and the flag is false to increase the counter if the counter > 3 we start updating
                if self._printer.is_printing() and not self.printing_job:
                    self.counter += 1
                    if self.counter > 3:
                        self._logger.warning(">>>!!!! Printing without all the Data? our safe counter reached >3 Double check info")

                        # M73 Based Information
                        if self._settings.get(["progress_type"]) == "m73_progress":
                            self._logger.info(f">>>+++ PrintStarted with M73 command enabled")
                            self.send_m73 = True

                        self.all_attributes_set(payload)  # Check if we have all the values

                if self.printing_job: # have a flag from the flow of Load -> Print -> Read -> Start so now we can Update or forced above.
                    self.update_print_info(payload)

            if event == "PrintDone":  # When Done change the screen and show the values
                e_time = self.get_elapsed_time()
                #self.send_O9000_cmd(f"UET|{e_time}")
                #self.send_O9000_cmd(f"UCL|{self.total_layers}")
                #self.send_O9000_cmd(f"UPP|100")

                self.send_O9001_cmd(f"O9001|ET:{e_time}|PG:100|CL:{str(self.total_layers_found).rjust(7, ' ')}")
                self.send_O9000_cmd(f"PF|")
                self.cleanup()

        def get_print_info(self, payload):  # Get the print info
            self._logger.info(f">>>>>> E3v3seprintjobdetailsPlugin Getting Print Details Info with counter value {self.counter}.")

            # Gather file_path from payload or printer's current job data
            self.file_path = payload.get("path") or self._printer.get_current_data().get("job", {}).get("file", {}).get("path")
            if self.file_path:
                self.file_path = self._file_manager.path_on_disk("local", self.file_path)
                self._logger.info(f"File selected: {self.file_path}")
            else:
                self._logger.warning("File path not found in payload or current job data.")
                return

            if not self.total_layers_known:
                self.total_layers = self.find_total_layers(self.file_path)
                self.total_layers_known = True

            if self.total_layers:
                self._logger.info(f"Total layers found: {self.total_layers}")
            else:
                self._logger.info("Total layers not found in the file setting a random Value.")
                self.total_layers = 666

            # Gather file_name from payload or printer's current job data
            self.file_name = payload.get("name") or self._printer.get_current_data().get("job", {}).get("file", {}).get("name", "DefaultName")

            self._logger.info(f"Checking if Print Time is set by M73: {self.print_time}")
            if self.print_time is None:
                # Gather print_time from printer's current job data
                self._logger.info(f"Print Time is not set by M73, getting from printer's current job data")
                self.print_time = self._printer.get_current_data().get("job", {}).get("estimatedPrintTime", "00:00:00")

                if self.print_time is not None:
                    self.print_time_known = True
                else:
                    self._logger.info(f">>>>>> E3v3seprintjobdetailsPlugin Print time still unknown")
                    self.print_time_known = False
                    return

            self._logger.info(f"Checking if Print Time Left is set by M73: {self.print_time_left}")
            if self.print_time_left is None:
                self._logger.info(f"Print Time Left is not set by M73, getting from printer's current job data")
                self.print_time_left = 0

            self._logger.info(f"Checking if Current Layer is set by M73: {self.current_layer}")
            if self.current_layer is None:
                self._logger.info(f"Current Layer is not set by M73, getting from printer's current job data")
                self.current_layer = 0

            self.progress = 0

            # If we have all the values we can send the info to the printer
            self._logger.info(f"Sending Print Info to the printer")
            self._logger.info(f"File selected: {self.file_name}")
            self._logger.info(f"Print Time: {self.print_time}")
            self._logger.info(f"Print Time Left: {self.print_time_left}")
            self._logger.info(f"current layer: {self.current_layer}")
            self._logger.info(f"progress: {self.progress}")
            self._logger.info(f"Print Time: {self.seconds_to_hms(self.print_time)}")
            self._logger.info(f"Print Time Left: {self.seconds_to_hms(self.print_time_left)}")

            # Send the print Info using custom O Command O9000 to the printer
            self.send_O9000_cmd(f"SFN|{self.file_name}")
            self.send_O9000_cmd(f"STL|{self.total_layers}")
            self.send_O9000_cmd(f"SCL|       0")
            self.send_O9000_cmd(f"SPT|{self.seconds_to_hms(self.print_time)}")
            self.send_O9000_cmd(f"SET|{self.seconds_to_hms(self.print_time)}")
            self.send_O9000_cmd(f"SPP|{self.progress}")
            self.send_O9000_cmd(f"SC|")

        def update_print_info(self, payload):  # Get info to Update
            self._logger.info(f">>>>>> E3v3seprintjobdetailsPlugin Update Print Details Info")
            self.print_time = self._printer.get_current_data().get("job", {}).get("estimatedPrintTime", "00:00:00")
            if (not self.print_time_known and (self.print_time != None)):
                # we know the print time now, so update it on the screen
                self.get_print_info(payload)
            elif (self.print_time == None):
                return

            self.print_time_left = self._printer.get_current_data().get("progress", {}).get("printTimeLeft", "00:00:00")
            #current_layer = self.layer_number

            if self.print_time_left is None or self.print_time_left == 0:
                self.print_time_left = self.print_time

            #if current_layer is None or current_layer == 0:
            #    current_layer = 0

            #only update if the print_time_left and progress changed
            if (self.prev_print_time_left != self.print_time_left or self.prev_layer_number != self.layer_number):

                # Lets render the Progress based on what the user wants. Either Layer or Time progress or M73 cmd.
                if self._settings.get(["progress_type"]) == "layer_progress":
                    # Progress is based on the layer
                    self.progress = (int(self.layer_number) *100 ) /int(self.total_layers)

                elif self._settings.get(["progress_type"]) == "m73_progress": # Progress based on M73 command not sending anything since is updated by terminal interception.
                    self._logger.info(f"Progress based on M73 command")
                    return
                else:
                    # Progress is kinda shitty when based on time, but its what it is
                    self.progress = (((self.print_time -self.print_time_left) /(self.print_time)) *100)

                self._logger.info(f"Print Time: {self.print_time}")
                self._logger.info(f"Print Time: {self.seconds_to_hms(self.print_time)}")
                self._logger.info(f"Print Time Left: {self.print_time_left}")
                self._logger.info(f"Print Time Left: {self.seconds_to_hms(self.print_time_left)}")
                self._logger.info(f"current layer: {self.layer_number}")
                self._logger.info(f"progress: {self.progress}")

                # Send the print Info using custom O Command O9001 to the printer
                self.prev_print_time_left = self.print_time_left
                self.prev_layer_number = self.layer_number
                #self.send_O9000_cmd(f"UET|{self.seconds_to_hms(self.print_time_left)}")
                #self.send_O9000_cmd(f"UPP|{self.progress}")
                self.myETA = self.seconds_to_hms(self.print_time_left)
                self._logger.info(f"O9001|ET:{self.myETA}|PG:{self.progress}|CL:{str(self.layer_number).rjust(7, ' ')}")

        def find_total_layers(self, file_path):
            # Find the Total Layer string in GCODE
            try:
                with open(file_path, "r") as gcode_file:
                    for line in gcode_file:
                        if "; total layer number:" in line:
                            # Extract total layers if Orca Generated
                            self.total_layers_found = line.strip().split(":")[-1].strip()
                            return self.total_layers_found
                        elif ";LAYER_COUNT:" in line:
                            # Extract total layers if Cura Generated
                            self.total_layers_found = line.strip().split(":")[-1].strip()
                            return self.total_layers_found
            except Exception as e:
                self._logger.error(f"Error reading file {file_path}: {e}")
                return None
            return None

        # Check if we have all Values
        def all_attributes_set(self, payload):

            self._logger.info(f">>>>>> E3v3seprintjobdetailsPlugin Checking if all attributes are set.")
            # Dictionary with attribute names and their values
            attributes = {
                "file_name": self.file_name,
                "file_path": self.file_path,
                "print_time": self.print_time,
                "print_time_left": self.print_time_left,
                "current_layer": self.current_layer,
                "progress": self.progress,
                "total_layers": self.total_layers,
            }

            # Identify attributes that are None
            none_attributes = [name for name, value in attributes.items() if value is None]

            # We are printing so we need to enable this
            self.printing_job = True
            # If there are no attributes with value None, returns True
            if not none_attributes:
                if self.current_layer == 0:
                    self.current_layer = 1

                self._logger.info("++++++ All attributes are set.")
                self._logger.info(f"File selected: {self.file_name}")
                self._logger.info(f"progress: {self.progress}")
                self._logger.info(f"current layer: {self.current_layer}")
                self.send_O9000_cmd(f"UCL|{str(self.layer_number).rjust(7, ' ')}")
                self.send_O9000_cmd(f"SC|") #force to render the screen with the values
                self._logger.info(f"Total layers found: {self.total_layers}")
                self._logger.info(f"Print Time: {self.seconds_to_hms(self.print_time)}")
                self._logger.info(f"Print Time Left: {self.seconds_to_hms(self.print_time_left)}")
                return
            else :
                self._logger.warning(f"Attributes not set: {none_attributes}")
                self._logger.warning(f"Payload: {payload}")
                self.current_layer = 1 # we are printing and layer must be 1
                self.get_print_info(payload)  # Try to get the info again

        #catch and parse commands
        #def gcode_queuing_handler(self, comm, phase, cmd, cmd_type, gcode, *args, **kwargs):
        def gcode_sending_handler(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):
            #self._logger.info(f"Intercepted G-code: {cmd}")

            # Intercept M73 commands to extract progress and time remaining
            if cmd.startswith("M73") and self._settings.get(["progress_type"]) == "m73_progress": #and self.send_m73:

                m73_match = re.match(r"M73 P(\d+)(?: R(\d+))?", cmd)
                if m73_match:
                    self.progress = int(m73_match.group(1))  # Extract progress (P)
                    remaining_minutes = int(m73_match.group(2)) if m73_match.group(2) else 0  # Extract remaining minutes (R), default to 0 if missing

                    # Convert remaining minutes to HH:MM:SS
                    hours, minutes = divmod(remaining_minutes, 60)
                    seconds = 0
                    remaining_time_hms = f"{hours:02}:{minutes:02}:{seconds:02}"

                    # Log and send the progress and remaining time
                    if self.progress == 0:
                        self.print_time = remaining_minutes *60
                        self.print_time_left = remaining_minutes *60
                        self.current_layer = 0
                        self.print_time_known = True
                        self._logger.info(f"====++++====++++==== Intercepted M73 P0: Setting the Print Time as={remaining_time_hms}")
                        self._logger.info(f"++++ M73 Set Print Time: {self.print_time}")
                        self._logger.info(f"++++ M73 Set Print Time Left: {self.print_time_left}")
                        self._logger.info(f"++++ M73 Set Current Layer: {self.current_layer}")
                        self.send_O9000_cmd(f"SPT|{remaining_time_hms}")
                    elif self.progress > 0 and self.send_m73:
                        self._logger.info(f"====++++====++++==== Intercepted M73: Progress={self.progress}%, Remaining Time={remaining_time_hms}")
                        #self.send_O9000_cmd(f"UPP|{self.progress}")  # Send progress
                        #self.send_O9000_cmd(f"UET|{remaining_time_hms}")  # Send remaining time
                        if self.prev_layer_number != self.layer_number:
                            self._logger.info(f"M73-O9001 Update: Progress={self.progress}%, ETA={remaining_time_hms}, Layer={self.layer_number}")
                            comm_instance._command_queue.put(f"O9001|ET:{remaining_time_hms}|PG:{self.progress}|CL:{str(self.layer_number).rjust(7, ' ')}")
                        #return [
                        #    cmd,
                        #    f"O9001|ET:{remaining_time_hms}|PG:{self.progress}|CL:{str(self.layer_number).rjust(7, ' ')}",
                        #]
                        #self.send_O9001_cmd(f"O9001|ET:{remaining_time_hms}|PG:{self.progress}|CL:{str(self.layer_number).rjust(7, ' ')}")

            # Detect the Layer Change
            if cmd.startswith("G1") and "Z" in cmd and self._settings.get(["progress_type"]) != "m73_progress":
                if self.prev_layer_number != self.layer_number:
                    self._logger.info(f"N-O9001 Update: Progress={self.progress}%, ETA={self.myETA}, Layer={self.layer_number}")
                    comm_instance._command_queue.put(f"O9001|ET:{self.myETA}|PG:{self.progress}|CL:{str(self.layer_number).rjust(7, ' ')}")
                #return [
                #    cmd,
                #     f"O9001|ET:{self.myETA}|PG:{self.progress}|CL:{str(self.layer_number).rjust(7, ' ')}"
                #]

            # Catch Commands to search the below...
            layer_comment_match = re.match(r"M117 DASHBOARD_LAYER_INDICATOR (\d+)", cmd)
            if layer_comment_match:
                # Extract Layer Number
                if layer_comment_match.group(1):
                    self.layer_number = int(layer_comment_match.group(1))
                else:
                    self.layer_number += 1  # If no number inc manually

                # send the layer number
                if self.printing_job:
                    self._logger.info(f"====++++====++++==== Layer Number: {self.layer_number}")
                #    self.send_O9000_cmd(f"UCL|{str(self.layer_number).rjust(7, ' ')}")

            # Ignoring any other M117 cmd if enabled
            elif cmd.startswith("M117"):

                # We want to write the cancelled MSG
                if cmd == "M117 Print is cancelled" or cmd == "M117 Print was cancelled":
                    return [cmd]

                if self._settings.get(["enable_o9000_commands"]):
                    self._logger.info(f"Ignoring M117 Command since this plugin has precedence to write to the LCD: {cmd}")
                    return []  #

            # Return the cmd
            return [cmd]

        # Send the O9000 comand to the printer
        def send_O9000_cmd(self, value):
            # self._logger.info(f"Trying to send command: O9000 {value}")
            if self._settings.get(["enable_o9000_commands"]):
                self._printer.commands(f"O9000 {value}")
                #time.sleep(0.15) # wait for the command to be sent

        # Send the O9001 comand to the printer
        def send_O9001_cmd(self, value):
            # self._logger.info(f"Trying to send command: O9000 {value}")
            if self._settings.get(["enable_o9000_commands"]):
                self._printer.commands(value)
                #time.sleep(0.15) # wait for the command to be sent

        # Classic function to change Seconds in to hh:mm:ss
        def seconds_to_hms(self, seconds_float):
            if not isinstance(seconds_float, (int, float)):
                seconds_float = 0
            seconds = int(round(seconds_float))
            hours = seconds //3600
            minutes = (seconds % 3600) //60
            seconds = seconds % 60
            return f"{hours:02}:{minutes:02}:{seconds:02}"

        def get_elapsed_time(self):
            if self.start_time is not None:
                self.elapsed_time = time.time() -self.start_time  # Get the elapsed time in seconds
                human_time = self.seconds_to_hms(self.elapsed_time)
                self._logger.info(f"Print ended at {time.ctime()} with elapsed time: {human_time}")
                self.start_time = None  # reset
                return human_time
            else:
                self._logger.warning("Print ended but no start time was recorded.")
                return "00:00:00"

        def cleanup(self):
            self.total_layers = 0
            self.was_loaded = False
            self.print_time_known = False
            self.total_layers_known = False
            self.prev_print_time_left = None
            self.prev_layer_number = None
            self.await_start = False
            self.await_metadata = False
            self.printing_job = False
            self.counter = 0
            self.start_time = None
            self.elapsed_time = None
            self.layer_number = 0
            self.send_m73 = False
            self.file_name = None
            self.file_path = None
            self.print_time = None
            self.print_time_left = None
            self.current_layer = None
            self.progress = None
            self.myETA = None
            self.total_layers_found = None

        def get_update_information(self):
            # Define the configuration for your plugin to use with the Software Update
            # Plugin here. See https://docs.octoprint.org/en/master/bundledplugins/softwareupdate.html
            # for details.
            return {
                "E3V3SEPrintJobDetails": {
                    "displayName": "E3v3seprintjobdetails Plugin",
                    "displayVersion": self._plugin_version,
                    # version check: github repository
                    "type": "github_release",
                    "user": "navaismo",
                    "repo": "OctoPrint-E3v3seprintjobdetails",
                    "current": self._plugin_version,
                    # update method: pip
                    "pip": "https://github.com/navaismo/OctoPrint-E3v3seprintjobdetails/archive/{target_version}.zip",
                }
            }


__plugin_pythoncompat__ = ">=3,<4"  # Only Python 3
__plugin_version__ = "0.0.1.9"


def __plugin_load__():
    global __plugin_implementation__
    __plugin_name__ = "E3v3seprintjobdetails"
    __plugin_implementation__ = E3v3seprintjobdetailsPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.comm.protocol.gcode.queuing": __plugin_implementation__.gcode_sending_handler
    }
