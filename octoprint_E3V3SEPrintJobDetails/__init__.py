# coding=utf-8
from __future__ import absolute_import
import re
import time
import octoprint.plugin

class E3v3seprintjobdetailsPlugin(octoprint.plugin.StartupPlugin,
                                      octoprint.plugin.EventHandlerPlugin,
                                      octoprint.plugin.SettingsPlugin,
                                      octoprint.plugin.TemplatePlugin
                                      ):

        def __init__(self): # init global vars
            self.total_layers = 0
            self.was_loaded = False
            self.print_time_known = False
            self.total_layers_known = False
            self.prev_print_time_left = None
            self.await_start = False
            self.await_metadata = False
            self.printing_job = False
            self.counter = 0
            self.start_time = None
            self.elapsed_time = None
            self.layer_number = 0
            self.send_m73 = False
            
            
        def get_settings_defaults(self):
            return dict(
                enable_o9000_commands=False,  # Default value for the slider.
                based_progress=False,
                m73_progress=False
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
            self._logger.info(f"Progress based on Layer: {self._settings.get(['based_progress'])}")
            self._logger.info(f"Progress based on M73 Command: {self._settings.get(['m73_progress'])}")

           
        def on_event(self, event, payload):
            self._logger.info(f">>>>>> E3v3seprintjobdetailsPlugin Event detected: {event}")  # Verify Events, Better to comment this
            
            
            if event == "Connected":
                self.send_O9000_cmd("OCON|")

            if event == "PrintCancelled":  # clean variables after cancellation
                self.cleanup()

            if event == "FileSelected":  # If file selected gather all data
                self.was_loaded = True
                time.sleep(0.5)
                self.await_start = True  # Lets Wait to complete
                self._logger.info(">>>>>> Loaded File, Waiting for PrintStarted")


            if event == "PrintStarted":
                self.slicer_values()
                self.start_time = time.time() # save the mark of the start
                if self.await_start and self.was_loaded:  # Are we waiting...
                    self._logger.info(f">>>+++ PrintStarted with Loaded File waiting for metadata")
                    self.await_metadata = True
                    time.sleep(.5)
                    self.get_print_info(payload)
                    
                    if self._settings.get(["m73_progress"]):
                        self._logger.info(f">>>+++ PrintStarted with M73 command enabled") 
                        self.send_m73 = True
                    
                if not self.was_loaded: # Direct print from GUI?
                    self._logger.info(">>>+++ PrintedStarted but File Not Loaded, wait for metadata")
                    self.await_metadata = True

            if event == "MetadataAnalysisFinished": 
                if self.await_metadata: # Metadata finished and we have a flag from the flow of Load -> Print -> Read -> Start
                    self._logger.info(">>>+++ PrintedStarted and Metadata Finish, get print Info")
                    time.sleep(.5)
                    self.printing_job = True
                    self.get_print_info(payload)

                    
            if event == "ZChange":  # Update the info every Z change
                # If the flow was a direct print from GUI: Print-> Start, and the file was already analized we will not have metadata step
                # So this is our insurance for a direct print of old file, a second print of existing analized file we will want to update all.
                # Check if the printer is printing and the flag is false to increase the counter if the counter > 3 we start updating 
                if self._printer.is_printing() and not self.printing_job:
                    self.counter += 1
                    if self.counter > 3:
                        self._logger.info(">>>!!!! Printing without all the Data, our safe counter reached >3")
                        if self._settings.get(["m73_progress"]):
                            self._logger.info(f">>>+++ PrintStarted with M73 command enabled") 
                            self.send_m73 = True
                        
                        #Doing the best to get the filepath at runtime
                        current_job = self._printer.get_current_job()
                        file_path = None
                        layers = 0
                        fn = None
                        # We have a file so lets get the info
                        if current_job and "file" in current_job:
                            fn = current_job["file"]["name"]
                            file_path = self._file_manager.path_on_disk("local", fn)
                            self._logger.info(f"got a path: {file_path}")
                            
                        else:
                            self._logger.info("Really not found a File?.")
                
                        #if we have a file then search for total layers... we can move this inside the above IF right? *shrugs* 
                        if file_path != None:
                            layers = self.find_total_layers(file_path)
                            self._logger.info(f"Layers found: {layers}")
                            self.total_layers = layers
                        else:
                            layers = 666 #The devil took our layers and helped us to not divide by 0 if you see the devil mark something wrong happened   
                            self._logger.info(f"The devil took our layers and helped us to not divide by 0 if you see the devil mark something wrong happened: {layers}")
                            self.total_layers = 666
                            
                        self.printing_job = True # we are printing without data :S, lets change that
                        self.print_time_known = True # we are updating already  & we dont want to go for the info it will fail anyway
                        self._logger.info(f"File selected: {fn}")
                        self._logger.info(f"Total Layers: {self.total_layers}") 
                        self._logger.info(f"Current Layer: {0}")
                        self._logger.info(f"Progress: {0}")
                        
                        # Send the print Info to render the screen, a little bit late but hey I'm not perfect.
                        self.send_O9000_cmd(f"SFN|{fn}")
                        time.sleep(.2)
                        self.send_O9000_cmd(f"STL|{self.total_layers}") # Bless our layers lord we are blind at this point and in your hands we are... godspeed!
                        time.sleep(.2)
                        self.send_O9000_cmd(f"SCL|       1") # should be 1 since the print just started now 
                        time.sleep(.2)
                        self.send_O9000_cmd(f"SC|") # Render the screen


                    
                if self.printing_job: # have a flag from the flow of Load -> Print -> Read -> Start so now we can Update or forced above. 
                    self.update_print_info(payload)


            if event == "PrintDone":  # When Done change the screen and show the values
                e_time = self.get_elapsed_time()
                self.send_O9000_cmd(f"UET|{e_time}")
                self.send_O9000_cmd(f"UCL|{self.total_layers}")
                self.send_O9000_cmd(f"UPP|100")
                self.send_O9000_cmd(f"PF|")
                self.cleanup()


        def get_print_info(self, payload):  # Get the print info
            self._logger.info(f">>>>>> E3v3seprintjobdetailsPlugin Getting Print Details Info 1st time.")
            time.sleep(0.9)
            file_path = self._file_manager.path_on_disk("local", payload.get("path"))
            self._logger.info(f"File selected: {file_path}")
            if (not self.total_layers_known):
                self.total_layers = self.find_total_layers(file_path)
                self.total_layers_known = True

            if self.total_layers:
                self._logger.info(f"Total layers found: {self.total_layers}")
            else:
                self._logger.info("Total layers not found in the file.")

            file_name = self._printer.get_current_data().get("job", {}).get("file", {}).get("name", "DefaultName")
            print_time = self._printer.get_current_data().get("job", {}).get("estimatedPrintTime", "00:00:00")
            if (print_time != None):
                self.print_time_known = True
            else:
                self._logger.info(f">>>>>> E3v3seprintjobdetailsPlugin Print time still unknown")
                return
            print_time_left = 0
            current_layer = 0
            progress = 0

            self._logger.info(f"File selected: {file_name}")
            self._logger.info(f"Print Time: {print_time}")
            self._logger.info(f"Print Time Left: {print_time_left}")
            self._logger.info(f"current layer: {current_layer}")
            self._logger.info(f"progress: {progress}")

            self._logger.info(f"Print Time: {self.seconds_to_hms(print_time)}")
            self._logger.info(f"Print Time Left: {self.seconds_to_hms(print_time_left)}")
            
            # Send the print Info using custom O Command O9000 to the printer
            self.send_O9000_cmd(f"SFN|{file_name}")
            self.send_O9000_cmd(f"STL|{self.total_layers}")
            self.send_O9000_cmd(f"SCL|       0")
            self.send_O9000_cmd(f"SPT|{self.seconds_to_hms(print_time)}")
            self.send_O9000_cmd(f"SET|{self.seconds_to_hms(print_time)}")
            self.send_O9000_cmd(f"SPP|{progress}")
            self.send_O9000_cmd(f"SC|")

        def update_print_info(self, payload):  # Get info to Update
            self._logger.info(f">>>>>> E3v3seprintjobdetailsPlugin Update Print Details Info")
            print_time = self._printer.get_current_data().get("job", {}).get("estimatedPrintTime", "00:00:00")
            if (not self.print_time_known and (print_time != None)):
                # we know the print time now, so update it on the screen
                self.get_print_info(payload)
            elif (print_time == None):
                return

            print_time_left = self._printer.get_current_data().get("progress", {}).get("printTimeLeft", "00:00:00")
            #current_layer = self.layer_number

            if print_time_left is None or print_time_left == 0:
                print_time_left = print_time

            #if current_layer is None or current_layer == 0:
            #    current_layer = 0

            #only update if the print_time_left and progress changed
            if (self.prev_print_time_left != print_time_left):
                
                # Lets render the Progress based on what the user wants. Either Layer or Time progress.
                if self._settings.get(["based_progress"]):
                    # Progress is based on the layer
                    progress = (int(self.layer_number) * 100 ) / int(self.total_layers)
                elif self._settings.get(["m73_progress"]):
                    self._logger.info(f"Progress based on M73 command") 
                    return                  
                else:
                    # Progress is kinda shitty when based on time, but its what it is
                    progress = (((print_time - print_time_left) / (print_time)) * 100)
    
    
                self._logger.info(f"Print Time: {print_time}")
                self._logger.info(f"Print Time: {self.seconds_to_hms(print_time)}")
                self._logger.info(f"Print Time Left: {print_time_left}")
                self._logger.info(f"Print Time Left: {self.seconds_to_hms(print_time_left)}")
                #self._logger.info(f"current layer: {current_layer}")
                self._logger.info(f"progress: {progress}")
                
                # Send the print Info using custom O Command O9000 to the printer
                self.prev_print_time_left = print_time_left
                self.send_O9000_cmd(f"UET|{self.seconds_to_hms(print_time_left)}")
                self.send_O9000_cmd(f"UPP|{progress}")


        def find_total_layers(self, file_path):
            # Find the Total Layer string in GCODE
            try:
                with open(file_path, "r") as gcode_file:
                    for line in gcode_file:
                        if "; total layer number:" in line:
                            # Extract total layers if Orca Generated
                            total_layers = line.strip().split(":")[-1].strip()
                            return total_layers
                        elif ";LAYER_COUNT:" in line:
                            # Extract total layers if Cura Generated
                            total_layers = line.strip().split(":")[-1].strip()
                            return total_layers
            except Exception as e:
                self._logger.error(f"Error reading file {file_path}: {e}")
                return None
            return None

        # Classic function to change Seconds in to hh:mm:ss
        def seconds_to_hms(self, seconds_float):
            if not isinstance(seconds_float, (int, float)):
                seconds_float = 0
            seconds = int(round(seconds_float))
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            seconds = seconds % 60
            return f"{hours:02}:{minutes:02}:{seconds:02}"

        def send_O9000_cmd(self, value):  # Send the comand to the printer
            # self._logger.info(f"Trying to send command: O9000 {value}")
            if self._settings.get(["enable_o9000_commands"]):
                self._printer.commands(f"O9000 {value}")


        #catch and parse commands
        def gcode_queuing_handler(self, comm, phase, cmd, cmd_type, gcode, *args, **kwargs):
            #self._logger.info(f"Intercepted G-code: {cmd}")
            
            # Intercept M73 commands to extract progress and time remaining
            if cmd.startswith("M73") and self._settings.get(["m73_progress"]) and self.send_m73:
                m73_match = re.match(r"M73 P(\d+)(?: R(\d+))?", cmd)
                if m73_match:
                    progress = int(m73_match.group(1))  # Extract progress (P)
                    remaining_minutes = int(m73_match.group(2)) if m73_match.group(2) else 0  # Extract remaining minutes (R), default to 0 if missing

                    # Convert remaining minutes to HH:MM:SS
                    hours, minutes = divmod(remaining_minutes, 60)
                    seconds = 0
                    remaining_time_hms = f"{hours:02}:{minutes:02}:{seconds:02}"

                    # Log and send the progress and remaining time
                    self._logger.info(f"====++++====++++==== Intercepted M73: Progress={progress}%, Remaining Time={remaining_time_hms}")
                    self.send_O9000_cmd(f"UPP|{progress}")  # Send progress
                    self.send_O9000_cmd(f"UET|{remaining_time_hms}")  # Send remaining time
                    
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
                    self.send_O9000_cmd(f"UCL|{str(self.layer_number).rjust(7, ' ')}")
            
            # Ignoring any other M117 cmd if enabled 
            elif cmd.startswith("M117"):
                
                # We want to write the cancelled MSG
                if cmd == "M117 Print is cancelled":
                    return [cmd]
                
                
                if self._settings.get(["enable_o9000_commands"]):
                    self._logger.info(f"Ignoring M117 Command since this plugin has precedence to write to the LCD: {cmd}")
                    return []  # 
    
            # Return the cmd
            return [cmd]


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
        
        def cleanup(self):
            self.total_layers = 0
            self.was_loaded = False
            self.print_time_known = False
            self.total_layers_known = False
            self.prev_print_time_left = None
            self.await_start = False
            self.await_metadata = False
            self.printing_job = False
            self.counter = 0
            self.start_time = None
            self.elapsed_time = None
            self.layer_number = 0
            self.send_m73 = False

        def get_elapsed_time(self):
            if self.start_time is not None:
                self.elapsed_time = time.time() - self.start_time  # Get the elapsed time in seconds
                human_time = self.seconds_to_hms(self.elapsed_time)
                self._logger.info(f"Print ended at {time.ctime()} with elapsed time: {human_time}")
                self.start_time = None  # reset
                return human_time
            else:
                self._logger.warning("Print ended but no start time was recorded.")    


__plugin_pythoncompat__ = ">=3,<4"  # Only Python 3
__plugin_version__ = "0.0.1.3"
      
def __plugin_load__():
    global __plugin_implementation__
    __plugin_name__ = "E3v3seprintjobdetails"
    __plugin_implementation__ = E3v3seprintjobdetailsPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.comm.protocol.gcode.queuing": __plugin_implementation__.gcode_queuing_handler
    }
