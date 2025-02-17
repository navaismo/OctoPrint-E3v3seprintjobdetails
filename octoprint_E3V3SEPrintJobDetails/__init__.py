# Coding=utf 8
from __future__ import absolute_import
import threading
from PIL import Image 
import io
import os
import re
import json
import time
import base64
import inspect
import octoprint.plugin
import octoprint.filemanager
import octoprint.filemanager.util


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
            self.prev_print_time_left = None
            self.prev_layer_number = None
            self.start_time = None
            self.elapsed_time = None
            self.file_name = None
            self.file_path = None
            self.print_time = None
            self.print_time_left = None
            self.progress = None
            self.myETA = None
            self.b64_thumb = None
            self.sent_metadata = False
            self.send_m73 = False
            self.was_loaded = False
            self.await_start = False
            self.printing_job = False
            self.is_lcd_ready = False
            self.counter = 0
            self.current_layer = 0
            self.total_layers = 0
            self.print_finish = False
            self.processing_file = False
            self.marlin_finished = False
            self.is_direct_print = False
            self.sent_imagemap = False
            
            
        def get_current_function_name(self):
            return inspect.getframeinfo(inspect.currentframe().f_back).function             

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
                self._logger.error(f"{self.get_current_function_name()}: Failed to save metadata to {metadata_path}: {e}") 
                
        # load metadata file                             
        def load_metadata_from_json(self, filename):
            metadata_path = self.metadata_dir + f"/{filename}.json"
            
            try:
                with open(metadata_path, "r") as metadata_file:
                    metadata = json.load(metadata_file)
                self._logger.info(f"Metadata loaded from {metadata_path}")
            
                return metadata
            except Exception as e:
                self._logger.error(f"{self.get_current_function_name()}: Failed to load metadata from {metadata_path}: {e}")
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
            self.b64_thumb = self.extract_thumbnail_from_content(file_content)
            
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
            "thumb_data": self.b64_thumb,
            "processed": True
            }
            
            self._logger.info(f">>>>>> E3v3seprintjobdetailsPlugin PreProcessing Metadata: {metadata}")
            
            # Store metadata
            try:
                self.save_metadata_to_json(self.file_name, metadata)
                self._logger.info(f"Metadata written for {path}")
            except Exception as e:
                self._logger.error(f"{self.get_current_function_name()}: Error writing metadata for {path}: {e}")
                        
            self._logger.info(f">>>>>> E3v3seprintjobdetailsPlugin PreProcessing Parsing complete for {self.file_name}")
            
            # Return the processed file without modifications
            return file_object 
        
        
        
        # Listen for the events
        def on_event(self, event, payload):
            #self._logger.info(f">>>>>> E3v3seprintjobdetailsPlugin Event detected: {event}")  # Verify Events, Better to comment this
             
            if event == "PrinterStateChanged":
                state = payload.get("state_id", "UNKNOWN")
                #self.file_name = payload.get("name")
                self._logger.info(f">>>>>> ++++ Intercepted state: {state}")
                if state == "STARTING": # Started the print
                    if not self.sent_metadata: # If we have already sent the metadata, we don't need to send it again
                        self._logger.info("Direct Print? Metadata not sent yet")
                        self.processing_file = True
                        self.is_direct_print = True
                        threading.Thread(target=self.get_print_metadata(self.file_name), daemon=True).start()
                    else:
                        self._logger.info("Metadata already sent, not a Direct Print")
                        
                        
            if event == "Connected":
                self.send_O9000_cmd("OCON|")
                #octob64 =["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"]
                #self.send_thumb_imagemap(octob64, "O9003")
                
            if event == "PrintCancelled":  # clean variables after cancellation
                self.cleanup()
                self.print_finish = True

            if event == "FileSelected":  # If file selected gather all data
                try:
                    self.file_name = payload.get("name")
                    self.file_path = payload.get("path")
                    
                    if not self.is_direct_print:
                        self.processing_file = True
                        self._logger.info("Not a Direct Print, Processing Metadata File")
                        self._logger.info("Set Lock for FileSelected")
                        threading.Thread(target=self.get_print_metadata(self.file_name), daemon=True).start()
                        self._plugin_manager.send_plugin_message(self._identifier, dict(action="disable_print_button", status="start"))
                  
                    self._logger.info(f">>>>>> Loaded File: {self.file_name}, Getting Metadata")    
                    # Start file processing in a separate thread to avoid blocking
                                       
                except Exception as e:
                    self._logger.error(f"{self.get_current_function_name()}: {e}")                    
                        
                    

            if event == "PrintStarted": #Job Print Started
                self.printing_job = True
                self.prev_layer_number = 0
                self.slicer_values()
                self._logger.info(f">>>+++ PrintStarted <<<<")
                self._logger.info(f">>>+++ File ready: {self.processing_file}")
                self._logger.info(f">>>+++ LCD ready: {self.is_lcd_ready}")
                self.start_time = time.time() # save the mark of the start
                    
                if self._settings.get(["progress_type"]) == "m73_progress":
                    self._logger.info(f">>>+++ PrintStarted with M73 command enabled")
                    self.send_m73 = True
                
                    
                    
                            
            if event == "ZChange":  # Update the info every Z change
                self._logger.info(f">>>>>> ZChange with:")
                self._logger.info(f"Print Finish: {self.print_finish}")
                self._logger.info(f"Printing Job: {self.printing_job}")
                self._logger.info(f"LCD Ready: {self.is_lcd_ready}")
                
                if not self.print_finish: 
                    if self.printing_job and self.is_lcd_ready:
                        if self._settings.get(["progress_type"]) != "m73_progress" and self.counter == 0:
                            #Not M73 print, we get the time from the printer job and set it
                            self.print_time = self._printer.get_current_data().get("job", {}).get("estimatedPrintTime", "00:00:00")
                            self.print_time_left = self.print_time
                            self.send_O9000_cmd(f"UPT|{self.seconds_to_hms(self.print_time_left)}")
                            self.send_O9001_cmd(f"O9001|ET:{self.seconds_to_hms(self.print_time_left)}|PG:{self.progress}|CL:{str(self.total_layers).rjust(7, ' ')}")
                            self.counter += 1
                        
                        #we are ready for updates
                        self.update_print_info(payload)        
                
                
            if event == "PrintDone":  # When Done change the screen and show the values
                e_time = self.get_elapsed_time()
                self.send_O9001_cmd(f"O9001|ET:{e_time}|PG:100|CL:{str(self.total_layers).rjust(7, ' ')}")
                self.send_O9000_cmd(f"PF|")
                self.cleanup()
                self.print_finish = True
        

        
        def get_print_metadata(self, file_name):
            try:
                self._logger.info(f">>>>>> Called get_print Metadata for {file_name}")
                md = None
                # Get all metadata 
                md = self.load_metadata_from_json(file_name)
                #self._logger.info(md)
                if md is None:
                    self._logger.error(f"{self.get_current_function_name()}: Error retrieving metadata for {file_name}")
                    return False
                
                self.file_name = md["file_name"]
                self.file_path = md["file_path"]
                self.total_layers = md["total_layers"]
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
                self._logger.info(f"Total Layers: {self.total_layers}")
                self._logger.info(f"current layer: {self.current_layer}")
                self._logger.info(f"progress: {self.progress}")

                # Send the print Info using custom O Command O9000 to the printer
                self.send_O9000_cmd(f"SFN|{self.file_name}")
                time.sleep(0.05)
                self.send_O9000_cmd(f"STL|{self.total_layers}")
                time.sleep(0.05)
                self.send_O9000_cmd(f"SCL|{str(self.current_layer).rjust(7, ' ')}")
                time.sleep(0.05)
                self.send_O9000_cmd(f"SPT|{self.print_time}")
                time.sleep(0.05)
                self.send_O9000_cmd(f"SET|{self.print_time}")
                time.sleep(0.05)
                self.send_O9000_cmd(f"SPP|{self.progress}")
                time.sleep(0.05)
                self.send_O9000_cmd(f"SC|")
                        
                # wait for the LCD to be ready        
                while not self.is_lcd_ready:
                    self._logger.info(f"Waiting for LCD to be ready, status: {self.is_lcd_ready}")
                    time.sleep(0.7)
                    
                # Send the thumbnail to the printer LCD READY.    
                self._logger.info(f">>>>>++++ LCD rendered all print info, sending GCode Thumbnail")
                self.sent_metadata = True
                time.sleep(0.2)
                
                if not self.sent_imagemap:
                    self.send_thumb_imagemap(self.b64_thumb, "O9002")
                
                return True
                    
            except Exception as e:
                self._logger.error(f"{self.get_current_function_name()}:  {e}")
                return False              
                    
                    
            
        def update_print_info(self, payload):  # Get info to Update
            self._logger.info(f">>>>>> E3v3seprintjobdetailsPlugin Update Print Details Info")
            
            if self.prev_layer_number != self.current_layer:
                # Lets render the Progress based on what the user wants. Either Layer or Time progress or M73 cmd.
                if self._settings.get(["progress_type"]) == "layer_progress":
                    # Progress is based on the layer
                    self.progress = (int(self.current_layer) *100 ) /int(self.total_layers)

                elif self._settings.get(["progress_type"]) == "m73_progress": # Progress based on M73 command not sending anything since is updated by terminal interception.
                    self._logger.info(f"Progress based on M73 command")
                    self.prev_layer_number = self.current_layer
                    return
                else:
                    # Progress is kinda shitty when based on time, but its what it is
                    self.progress = (((self.print_time -self.print_time_left) /(self.print_time)) *100)

                self._logger.info(f"Print Time: {self.print_time}")
                self._logger.info(f"Print Time: {self.seconds_to_hms(self.print_time)}")
                self._logger.info(f"Print Time Left: {self.print_time_left}")
                self._logger.info(f"Print Time Left: {self.seconds_to_hms(self.print_time_left)}")
                self._logger.info(f"current layer: {self.current_layer}")
                self._logger.info(f"progress: {self.progress}")

                # Send the print Info using custom O Command O9001 to the printer
                self.prev_layer_number = self.current_layer
                self.myETA = self.seconds_to_hms(self.print_time_left)
                self._logger.info(f"O9001|ET:{self.myETA}|PG:{self.progress}|CL:{str(self.current_layer).rjust(7, ' ')}")


        #catch and parse commands
       
        def gcode_sending_handler(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):
            #self._logger.info(f"Intercepted G-code: {cmd}")
            # Intercept M73 commands to extract progress and time remaining
            if cmd.startswith("M73") and self._settings.get(["progress_type"]) == "m73_progress":
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
                        self.print_time = remaining_minutes * 60
                        self.print_time_left = remaining_minutes * 60
                        self.current_layer = 0
                        self.print_time_known = True
                        self._logger.info(f"====++++====++++==== Intercepted M73 P0: Setting the Print Time as={remaining_time_hms}")
                        self._logger.info(f"++++ M73 Set Print Time: {remaining_time_hms}")
                        self._logger.info(f"++++ M73 Set Print Time Left: {remaining_time_hms}")
                        self._logger.info(f"++++ M73 Set Current Layer: {self.current_layer}")
                        self.send_O9000_cmd(f"SPT|{remaining_time_hms}")
                    elif self.progress > 0 and self.send_m73:
                        self._logger.info(f"====++++====++++==== Intercepted M73: Progress={self.progress}%, Remaining Time={remaining_time_hms}")
                        if self.prev_layer_number != self.current_layer:
                            self._logger.info(f"M73-O9001 Update: Progress={self.progress}%, ETA={remaining_time_hms}, Layer={self.current_layer}")
                            comm_instance._command_queue.put(f"O9001|ET:{remaining_time_hms}|PG:{self.progress}|CL:{str(self.current_layer).rjust(7, ' ')}")

            # Detect the Layer Change
            if cmd.startswith("G1") and "Z" in cmd and self._settings.get(["progress_type"]) != "m73_progress":
                if self.prev_layer_number != self.current_layer:
                    self._logger.info(f"N-O9001 Update: Progress={self.progress}%, ETA={self.myETA}, Layer={self.current_layer}")
                    comm_instance._command_queue.put(f"O9001|ET:{self.myETA}|PG:{self.progress}|CL:{str(self.current_layer).rjust(7, ' ')}")

            # Catch Commands to search the below...
            layer_comment_match = re.match(r"M117 DASHBOARD_LAYER_INDICATOR (\d+)", cmd)
            if layer_comment_match:
                # Extract Layer Number
                if layer_comment_match.group(1):
                    self.current_layer = int(layer_comment_match.group(1))
                else:
                    self.current_layer += 1  # If no number inc manually

                # send the layer number
                if self.printing_job:
                    self._logger.info(f"====++++====++++==== Layer Number: {self.current_layer}")

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
        
        
        
        
        def gcode_received_handler(self, comm, line, *args, **kwargs):
            #self._logger.info(f"========== >>>>>  Received G-code response: {line}")
            # Process the response 
            if line.startswith("O9000"):
                self._logger.info(f"Processing O9000 response: {line}")
                # check if we received the string "sc-rendered" from command O9000 sc-rendered
                if "sc-rendered" in line:
                    self._logger.info(f"Screen rendered in LCD")
                    self.is_lcd_ready = True
                    return line
                
                elif "thumbnail rendered" in line:
                    self._logger.info(f"Marlin Finished processing, resuming the print")
                    if self._printer.is_paused():
                        self._printer.resume_print()
                
            return line
        
    
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
                
        # Send the O9002 comand to the printer
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
                            self.total_layers = line.strip().split(":")[-1].strip()
                            return self.total_layers
                        elif ";LAYER_COUNT:" in line:
                            # Extract total layers if Cura Generated
                            self.total_layers = line.strip().split(":")[-1].strip()
                            return self.total_layers
            except Exception as e:
                self._logger.error(f"{self.get_current_function_name()}: Error reading file {file_path}: {e}")
                return None
            return None
        

        # send the preview to LCD
        def send_thumb_imagemap(self, b64, o_cmd):
            self._logger.info(f">>>>>> E3v3seprintjobdetailsPlugin Sending Thumbnail Image Map")
            if b64:
                self._logger.info("Thumbnail data found in the file.")
                self._logger.info(f"Thumbnail data: {b64}")
                # Decode Base64 and send it to Marlin
                img = self.decode_base64_image(b64[0])
                pixel_data = self.get_pixel_data(img)
                self._logger.info(f"Pixel data length: {len(pixel_data)}")
                # Ensure the pixel_data has the correct size for a 96x96 image
                expected_size = 0
                if o_cmd == "O9002":
                    expected_size = 96 * 96
                else:
                    expected_size = 26 * 240
                
                if len(pixel_data) != expected_size:
                    raise ValueError(f"{self.get_current_function_name()}: Expected pixel data size {expected_size}, but got {len(pixel_data)}")
                
                self.send_image_to_marlin(pixel_data, o_cmd)
            else:
                self._logger.warning("Thumbnail data not found in the file.")
                return    
       
            
        def send_image_to_marlin(self, pixel_data, o_cmd):
            self._printer.pause_print() #TODO check if this pause is necessary  
            chunk_size = 12  # Adjust as needed to stay below the 64-byte limit
            self._logger.info(f"Sending Pixel Data to Marlin using CHUNKs of {chunk_size}")
            
            try:
                # Send final end-of-data command
                self._printer.commands(f"{o_cmd} START 96 96")
                time.sleep(0.2)
                for i in range(0, len(pixel_data), chunk_size):
                    chunk = pixel_data[i:i + chunk_size]
                    # Create a command with a chunk offset followed by pixel data
                    command = f"{o_cmd} CHUNK {i}|{','.join(map(str, chunk))}"
                    self._printer.commands(command)  # Send the chunk command to Marlin
                    time.sleep(0.06)  # Small delay to avoid overflowing Marlin's buffer
                
                # Send final end-of-data command
                self._printer.commands(f"{o_cmd} END")
            
                self._logger.info("Pixel Data sent successfully to Marlin")
                self._logger.info("Resuming the print job")
                self.processing_file = False
                self.marlin_finished = True
                self.sent_imagemap = True
                
                if self._printer.is_paused():
                    self._logger.info(">>> Printer is paused. Resuming print job now.")
                    self._printer.resume_print()
                
                
            except Exception as e:
                self._logger.error(f"{self.get_current_function_name()}: Error sending pixel data to Marlin: {e}")
                        

        # Decode Base64 image to raw pixel data
        def decode_base64_image(self, b64_string):
            image_data = base64.b64decode(b64_string)  # Decode Base64
            image = Image.open(io.BytesIO(image_data))  # Open image with Pillow
            return image
        
        #get array map
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
                    self.total_layers = line.strip().split(":")[-1].strip()
                    return self.total_layers
                elif ";LAYER_COUNT:" in line:
                    # Extract total layers if Cura Generated
                    self.total_layers = line.strip().split(":")[-1].strip()
                    return self.total_layers
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
                        self.print_time = remaining_time_hms
                        self.print_time_left = remaining_time_hms
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
            #self.plugin_data_folder = None
            #self.metadata_dir = None
            self.prev_print_time_left = None
            self.prev_layer_number = None
            self.start_time = None
            self.elapsed_time = None
            self.file_name = None
            self.file_path = None
            self.print_time = None
            self.print_time_left = None
            self.progress = None
            self.myETA = None
            self.b64_thumb = None
            self.sent_metadata = False
            self.send_m73 = False
            self.printing_job = False
            self.is_lcd_ready = False
            self.counter = 0
            self.current_layer = 0
            self.total_layers = 0
            self.print_finish = False
            self.processing_file = False
            self.marlin_finished = False
            self.is_direct_print = False
            self.sent_imagemap = False
           


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
__plugin_version__ = "0.0.2.0"


def __plugin_load__():
    global __plugin_implementation__
    __plugin_name__ = "E3v3seprintjobdetails"
    __plugin_implementation__ = E3v3seprintjobdetailsPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.filemanager.preprocessor": __plugin_implementation__.file_preprocessor,
        "octoprint.comm.protocol.gcode.queuing": __plugin_implementation__.gcode_sending_handler,
        "octoprint.comm.protocol.gcode.received": __plugin_implementation__.gcode_received_handler,
        
    }
