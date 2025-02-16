# Coding=utf 8
from __future__ import absolute_import
import re
import time
import base64
from PIL import Image, ImageChops, ImageEnhance
import io
import octoprint.plugin
import octoprint.filemanager
import octoprint.filemanager.util
import json
import os


class E3v3seprintjobdetailsPlugin(octoprint.plugin.StartupPlugin,
                                  octoprint.filemanager.util.LineProcessorStream,
                                  octoprint.plugin.EventHandlerPlugin,
                                  octoprint.plugin.ProgressPlugin,
                                  octoprint.plugin.SettingsPlugin,
                                  octoprint.plugin.TemplatePlugin
                                  ):
    
        

        def __init__(self): # init global vars
            
            self.plugin_data_folder = None
            self.metadata_dir = None
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
            self.b64_thumb = None
            self.LCD_COLORS = {
                "black":  0x0841,
                "blue":   0x19FF,
                "red":    0xF44F,
                "yellow": 0xFE29,
                "white":  0xFFFF
            }
            
            

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
            # Get the plugin's data folder (OctoPrint manages this)
            data_folder = self.get_plugin_data_folder()
            
            # Define the metadata subdirectory
            self.metadata_dir = os.path.join(data_folder, "metadata")
            
            # Create the directory if it doesn't exist
            os.makedirs(self.metadata_dir, exist_ok=True)
            os.chmod(self.metadata_dir, 0o775)
    
            self._logger.info(f">>>>>> E3v3seprintjobdetailsPlugin Metadata directory initialized: {self.metadata_dir}")
            self.slicer_values()

        def slicer_values(self):
            self._logger.info(f"Plugin Version: {self._plugin_version}")
            self._logger.info(f"Sliders values:")
            self._logger.info(f"Enable O9000 Commands: {self._settings.get(['enable_o9000_commands'])}")
            self._logger.info(f"Progress based on: {self._settings.get(['progress_type'])}")


        # save metadata of the file
        def save_metadata_to_json(self, filename, metadata):
            metadata_path = self.metadata_dir + f"/{filename}.json"
            
            try:    
                with open(metadata_path, "w") as metadata_file:
                    json.dump(metadata, metadata_file)
                self._logger.info(f"Metadata saved to {metadata_path}")
            
            except Exception as e:
                self._logger.error(f"Failed to save metadata to {metadata_path}: {e}") 
                
        # load metadata file                             
        def load_metadata_from_json(self, filename):
            metadata_path = self.metadata_dir + f"/{filename}.json"
            
            try:
                with open(metadata_path, "r") as metadata_file:
                    metadata = json.load(metadata_file)
                self._logger.info(f"Metadata loaded from {metadata_path}")
            
                return metadata
            except Exception as e:
                self._logger.error(f"Failed to load metadata from {metadata_path}: {e}")
                return None

        # preprocess the file to get details.
        def file_preprocessor(self, path, file_object, links, printer_profile, allow_overwrite, *args, **kwargs):
            """Intercept file uploads and process them before allowing selection or printing."""
            self._logger.info(f">>>>>> E3v3seprintjobdetailsPlugin PreProcessing file: {file_object}")
            self._logger.info(f">>>>>> E3v3seprintjobdetailsPlugin PreProcessing path: {path}")
             
            if not octoprint.filemanager.valid_file_type(path, type="gcode"):
                return file_object
            
            self.file_name = file_object.filename
             
            # Read the file content from the stream
            file_stream = file_object.stream()
            file_content = file_stream.read().decode('utf-8')
            
            # obtain the data from stream
            self.total_layers = self.find_total_layers_from_content(file_content)
            self._logger.info(f">>>>>> E3v3seprintjobdetailsPlugin PreProcessing Total Layers: {self.total_layers}")
            self.thumb_data = self.extract_thumbnail_from_content(file_content)
            
            if self._settings.get(["progress_type"]) == "m73_progress":
                self.progress, self.myETA = self.find_first_m73_from_content(file_content)
                self.print_time = self.myETA
            else:
                self.progress = 0
                self.myETA = "00:00:00"
                self.print_time = "00:00:00"    
            
            # save into object
            metadata = {
            "file_name": self.file_name,
            "file_path": path,   
            "total_layers": self.total_layers,  
            "print_time": self.print_time,  
            "print_time_left": self.print_time,
            "current_layer": 0,
            "progress": self.progress,
            "thumb_data": self.thumb_data,
            "processed": True
            }
            
            self._logger.info(f">>>>>> E3v3seprintjobdetailsPlugin PreProcessing Metadata: {metadata}")
            
            # Store metadata
            try:
                self.save_metadata_to_json(self.file_name, metadata)
                self._logger.info(f"Metadata written for {path}")
            except Exception as e:
                self._logger.error(f"Error writing metadata for {path}: {e}")
                        
            self._logger.info(f">>>>>> E3v3seprintjobdetailsPlugin PreProcessing Parsing complete for {self.file_name}")
            
            # Return the processed file without modifications
            return file_object 
        
        
        
        # Listen for the events
        def on_event(self, event, payload):
            self._logger.info(f">>>>>> E3v3seprintjobdetailsPlugin Event detected: {event}")  # Verify Events, Better to comment this

            if event == "Connected":
                self.send_O9000_cmd("OCON|")

            if event == "PrintCancelled":  # clean variables after cancellation
                self.cleanup()

            if event == "FileSelected":  # If file selected gather all data
                self._logger.info(">>>>>> Loaded File, Getting Metadata")
                # Get filename and path from payload
                file_name = payload.get("name")
                file_path = payload.get("path")
                        
                try:
                    # Get all metadata 
                    md = self.load_metadata_from_json(file_path)
                    #self._logger.info(md)
    
                    self.file_name = md["file_name"]
                    self.file_path = md["file_path"]
                    self.total_layers_found = md["total_layers"]
                    self.print_time =  md["print_time"]
                    self.print_time_left = md["print_time_left"]
                    self.current_layer = md["current_layer"]
                    self.progress = md["progress"]
                    self.b64_thumb = md["thumb_data"]
                    
                     # If we have all the values we can send the info to the printer
                    self._logger.info(f"Sending Print Info")
                    self._logger.info(f"File selected: {self.file_name}")
                    self._logger.info(f"Print Time: {self.print_time}")
                    self._logger.info(f"Print Time Left: {self.print_time_left}")
                    self._logger.info(f"current layer: {self.current_layer}")
                    self._logger.info(f"progress: {self.progress}")

                    # Send the print Info using custom O Command O9000 to the printer
                    self.send_O9000_cmd(f"SFN|{self.file_name}")
                    self.send_O9000_cmd(f"STL|{self.total_layers}")
                    self.send_O9000_cmd(f"SCL|{str(self.current_layer).rjust(7, ' ')}")
                    self.send_O9000_cmd(f"SPT|{self.print_time}")
                    self.send_O9000_cmd(f"SET|{self.print_time}")
                    self.send_O9000_cmd(f"SPP|{self.progress}")
                    self.send_O9000_cmd(f"SC|")
                    # Send the image map
                    self.send_thumb_imagemap(self.b64_thumb)
                    
                    
                    
                except Exception as e:
                    self._logger.error(f"Error retrieving metadata for {file_path}: {e}")
                    return None              
                        
                #self.send_O9000_cmd("SC|")
                #self.send_thumb_imagemap(payload)

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
                
        # Send the O9001 comand to the printer
        def send_O9002_cmd(self, value):
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
        
        
        def find_first_m73(self, file_path):
            try:
                with open(file_path, "r") as gcode_file:
                    for line in gcode_file:
                        m73_match = re.match(r"M73 P(\d+)(?: R(\d+))?", line)
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
                                return self.progress, remaining_time_hms   
                            
            except Exception as e:
                self._logger.error(f"Error reading file {file_path}: {e}")
                return None
            return None
        
        
        def extract_thumbnail(self, file_path):
            thumbnails = []
            collecting = False
            current_thumbnail = []

            with open(file_path, 'r', encoding='utf-8') as file:
                for line in file:
                    line = line.strip()  # Remove leading/trailing whitespace
                    
                    if line.startswith("; THUMBNAIL_BLOCK_START"):
                        collecting = False  # Reset flag in case of multiple blocks

                    if collecting:
                        if line.startswith("; thumbnail_JPG end"):
                            thumbnails.append("".join(current_thumbnail))
                            current_thumbnail = []
                            collecting = False
                            continue  # Stop collecting until next valid block
                        else:
                            # Remove leading "; " before storing data
                            cleaned_line = line.lstrip("; ").rstrip()
                            current_thumbnail.append(cleaned_line)

                    if line.startswith("; thumbnail_JPG begin 96x96"):
                        collecting = True  # Start collecting

            return thumbnails



        def send_thumb_imagemap(self, b64):
            self._logger.info(f">>>>>> E3v3seprintjobdetailsPlugin Sending Thumbnail Image Map")
            #self.file_path = payload.get("path") or self._printer.get_current_data().get("job", {}).get("file", {}).get("path")
        #if self.file_path:
        #    self.file_path = self._file_manager.path_on_disk("local", self.file_path)
        #    self._logger.info(f"File selected: {self.file_path}")
            
            # Get the thumbnail data from the G-code file
            #thumbnail_data = self.extract_thumbnail(self.file_path)
            if b64:
                self._logger.info("Thumbnail data found in the file.")
                self._logger.info(f"Thumbnail data: {b64}")
                # Decode Base64 and send it to Marlin
                img = self.decode_base64_image(b64[0])
                pixel_data = self.get_pixel_data(img)
                self._logger.info(f"Pixel data length: {len(pixel_data)}")
                # Ensure the pixel_data has the correct size for a 96x96 image
                expected_size = 96 * 96
                if len(pixel_data) != expected_size:
                    raise ValueError(f"Expected pixel data size {expected_size}, but got {len(pixel_data)}")
                
                self.send_image_to_marlin(pixel_data)
            else:
                self._logger.warning("Thumbnail data not found in the file.")
                return    
        #else:
        #    self._logger.warning("File path not found in payload or current job data.")
        #    return
            


        def send_image_to_marlin(self, pixel_data):
            chunk_size = 10  # Adjust as needed to stay below the 64-byte limit
            self._logger.info(f"Sending Pixel Data to Marlin using CHUNKs of {chunk_size}")
            
            try:
                # Send final end-of-data command
                self.send_O9002_cmd("O9002 START 96 96")
                time.sleep(0.2)
                for i in range(0, len(pixel_data), chunk_size):
                    chunk = pixel_data[i:i + chunk_size]
                    # Create a command with a chunk offset followed by pixel data
                    command = f"O9002 CHUNK {i}|{','.join(map(str, chunk))}"
                    self.send_O9002_cmd(command)  # Send the chunk command to Marlin
                    time.sleep(0.05)  # Small delay to avoid overflowing Marlin's buffer
                
                # Send final end-of-data command
                self.send_O9002_cmd("O9002 END")
                self._logger.info("Pixel Data sent successfully to Marlin")
            except Exception as e:
                self._logger.error(f"Error sending pixel data to Marlin: {e}")
                            


        # Function to map grayscale to nearest LCD color
        def map_to_nearest_color(self, pixel):
            threshold = 128
            if pixel < 50:
                return self.LCD_COLORS["black"]
            elif pixel < 100:
                return self.LCD_COLORS["blue"]
            elif pixel < 150:
                return self.LCD_COLORS["red"]
            elif pixel < 200:
                return self.LCD_COLORS["yellow"]
            return self.LCD_COLORS["white"]


        # Decode Base64 image to raw pixel data
        def decode_base64_image(self, b64_string):
            image_data = base64.b64decode(b64_string)  # Decode Base64
            image = Image.open(io.BytesIO(image_data))  # Open image with Pillow
            return image
        
        
        # Remove background from the image
        def remove_background(self, image):
            # Convert image to grayscale
            grayscale_image = image.convert("L")
            # Enhance the contrast to make background removal easier
            enhancer = ImageEnhance.Contrast(grayscale_image)
            enhanced_image = enhancer.enhance(2.0)
            # Create a binary mask where the background is white
            binary_mask = enhanced_image.point(lambda p: p > 200 and 255)
            # Invert the mask
            inverted_mask = ImageChops.invert(binary_mask)
            # Apply the mask to the original image
            image_with_transparency = image.convert("RGBA")
            image_with_transparency.putalpha(inverted_mask)
            return image_with_transparency

        # Convert image to grayscale and map to black and white
        def convert_to_black_and_white(self, image):
            grayscale_image = image.convert("L")  # Convert image to grayscale
            pixel_values = list(grayscale_image.getdata())  # Get pixel values
            return [self.map_to_nearest_color(pixel) for pixel in pixel_values]  # Map to nearest LCD color

    
        def get_pixel_data(self, image):
            img = image.convert('RGB')  # Ensure RGB mode
            width, height = img.size
            imgbytes = img.tobytes()

            # Create the pixel map array
            pixel_map = []

            for y in range(height):
                for x in range(width):
                    idx = (y * width + x) * 3
                    r_scaled = (imgbytes[idx]     * 31) // 255
                    g_scaled = (imgbytes[idx + 1] * 63) // 255
                    b_scaled = (imgbytes[idx + 2] * 31) // 255
                    color16bit = (r_scaled << 11) | (g_scaled << 5) | b_scaled
                    pixel_map.append(color16bit)  # Save pixel in the map

            return pixel_map    
        
        
        
        
        def find_total_layers_from_content(self, file_content):
            # Find the Total Layer string in GCODE content
            for line in file_content.splitlines():
                if "; total layer number:" in line:
                    # Extract total layers if Orca Generated
                    self.total_layers_found = line.strip().split(":")[-1].strip()
                    return self.total_layers_found
                elif ";LAYER_COUNT:" in line:
                    # Extract total layers if Cura Generated
                    self.total_layers_found = line.strip().split(":")[-1].strip()
                    return self.total_layers_found
            return None

        def find_first_m73_from_content(self, file_content):
            for line in file_content.splitlines():
                m73_match = re.match(r"M73 P(\d+)(?: R(\d+))?", line)
                if m73_match:
                    self.progress = int(m73_match.group(1))  # Extract progress (P)
                    remaining_minutes = int(m73_match.group(2)) if m73_match.group(2) else 0  # Extract remaining minutes (R), default to 0 if missing
                    # Convert remaining minutes to HH:MM:SS
                    hours, minutes = divmod(remaining_minutes, 60)
                    seconds = 0
                    remaining_time_hms = f"{hours:02}:{minutes:02}:{seconds:02}"

                    # Log and send the progress and remaining time
                    if self.progress == 0:
                        self.print_time = remaining_minutes * 60
                        self.print_time_left = remaining_minutes * 60
                        self.current_layer = 0
                        self.print_time_known = True
                        return self.progress, remaining_time_hms
            return 0, "00:00:00"

        def extract_thumbnail_from_content(self, file_content):
            thumbnails = []
            collecting = False
            current_thumbnail = []

            for line in file_content.splitlines():
                line = line.strip()  # Remove leading/trailing whitespace
                
                if line.startswith("; THUMBNAIL_BLOCK_START"):
                    collecting = False  # Reset flag in case of multiple blocks

                if collecting:
                    if line.startswith("; thumbnail_JPG end"):
                        thumbnails.append("".join(current_thumbnail))
                        current_thumbnail = []
                        collecting = False
                        continue  # Stop collecting until next valid block
                    else:
                        # Remove leading "; " before storing data
                        cleaned_line = line.lstrip("; ").rstrip()
                        current_thumbnail.append(cleaned_line)

                if line.startswith("; thumbnail_JPG begin 96x96"):
                    collecting = True  # Start collecting

            return thumbnails

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
__plugin_version__ = "0.0.1.9TH1"


def __plugin_load__():
    global __plugin_implementation__
    __plugin_name__ = "E3v3seprintjobdetails"
    __plugin_implementation__ = E3v3seprintjobdetailsPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
         "octoprint.filemanager.preprocessor": __plugin_implementation__.file_preprocessor,
        "octoprint.comm.protocol.gcode.queuing": __plugin_implementation__.gcode_sending_handler
    }
