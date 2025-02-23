$(function() {
    function E3v3seprintjobdetailsViewModel(parameters) {
        var self = this;

        function showPopup(message) {
            console.log("Attempting to show popup:", message);
        
            // If modal does not exist, create it
            if ($("#customPopup").length === 0) {
                $("body").append(`
                    <div id="customPopup" class="modal fade" tabindex="-1" role="dialog">
                        <div class="modal-dialog modal-dialog-centered" role="document">
                            <div class="modal-content" style="border-radius: 10px; overflow: hidden;">
                                <div class="modal-header" style="background: linear-gradient(135deg, #007bff, #6610f2); color: white;">
                                    <h5 class="modal-title">
                                        <i class="fas fa-info-circle"></i> Processing Request
                                    </h5>
                                    <button type="button" class="close" data-dismiss="modal" aria-label="Close" style="color: white; opacity: 0.8;">
                                        <span aria-hidden="true">&times;</span>
                                    </button>
                                </div>
                                <div class="modal-body text-center">
                                    <p id="customPopupMessage" class="mb-3" style="font-size: 16px; font-weight: 500;"></p>
                                    <div class="spinner">
                                        <div class="double-bounce1"></div>
                                        <div class="double-bounce2"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `);
        
                // Add custom CSS styles
                $("head").append(`
                    <style>
                        .spinner {
                            width: 50px;
                            height: 50px;
                            position: relative;
                            margin: 0 auto;
                        }
        
                        .double-bounce1, .double-bounce2 {
                            width: 100%;
                            height: 100%;
                            border-radius: 50%;
                            background-color: #007bff;
                            opacity: 0.6;
                            position: absolute;
                            top: 0;
                            left: 0;
                            animation: bounce 2.0s infinite ease-in-out;
                        }
        
                        .double-bounce2 {
                            animation-delay: -1.0s;
                        }
        
                        @keyframes bounce {
                            0%, 100% { transform: scale(0.0); }
                            50% { transform: scale(1.0); }
                        }
                    </style>
                `);
            }

            // Set the message and show the modal
            $("#customPopupMessage").text(message);
            $("#customPopup").modal("show");
        }

        function closePopup() {
            console.log("Closing popup...");
            $("#customPopup").modal("hide");
        }

        function closeErrorPopup() {
            console.log("Closing popup...");
            $("#errorPopup").modal("hide");
        }

        function showErrorPopup(message) {
            console.log("Attempting to show error popup:", message);
        
            // If modal does not exist, create it
            if ($("#errorPopup").length === 0) {
                $("body").append(`
                    <div id="errorPopup" class="modal fade" tabindex="-1" role="dialog">
                        <div class="modal-dialog modal-dialog-centered" role="document">
                            <div class="modal-content" style="border-radius: 10px; overflow: hidden;">
                                <div class="modal-header" style="background: linear-gradient(135deg, #dc3545, #b30000); color: white;">
                                    <h5 class="modal-title">
                                        <i class="fas fa-exclamation-triangle"></i> Error Occurred
                                    </h5>
                                    <button type="button" class="close" data-dismiss="modal" aria-label="Close" style="color: white; opacity: 0.8;">
                                        <span aria-hidden="true">&times;</span>
                                    </button>
                                </div>
                                <div class="modal-body text-center">
                                    <p id="errorPopupMessage" class="mb-3" style="font-size: 16px; font-weight: 500;"></p>
                                    <div class="error-animation">
                                        <div class="circle"></div>
                                        <div class="cross">
                                            <div class="cross-line"></div>
                                            <div class="cross-line"></div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `);
        
                // Add custom CSS styles
                $("head").append(`
                    <style>
                        .error-animation {
                            position: relative;
                            width: 50px;
                            height: 50px;
                            margin: 0 auto;
                        }
        
                        .circle {
                            width: 100%;
                            height: 100%;
                            border-radius: 50%;
                            background-color: #dc3545;
                            opacity: 0.7;
                            position: absolute;
                            top: 0;
                            left: 0;
                            animation: pulse 1.5s infinite;
                        }
        
                        .cross {
                            position: absolute;
                            top: 50%;
                            left: 50%;
                            transform: translate(-50%, -50%) rotate(45deg);
                        }
        
                        .cross-line {
                            position: absolute;
                            width: 40px;
                            height: 5px;
                            background-color: white;
                            border-radius: 5px;
                        }
        
                        .cross-line:nth-child(2) {
                            transform: rotate(90deg);
                        }
        
                        @keyframes pulse {
                            0% { transform: scale(1); opacity: 0.7; }
                            50% { transform: scale(1.2); opacity: 0.5; }
                            100% { transform: scale(1); opacity: 0.7; }
                        }
                    </style>
                `);
            }
        
            // Set the message and show the modal
            $("#errorPopupMessage").text(message);
            $("#errorPopup").modal("show");
        }
        








        self.onDataUpdaterPluginMessage = function(plugin, data) {
            console.log(">>> Received plugin message from:", plugin, "Data:", data);
            if (plugin !== "E3V3SEPrintJobDetails") return;

            if (data.type === "popup") {
                //console.log(">>> Showing popup with message:", data.message);
                showPopup(data.message);
            } else if (data.type === "close_popup") {
                closePopup();
            } else if (data.type === "error_popup") {
                showErrorPopup(data.message);
            } else if (data.type === "close_error_popup") {
                closeErrorPopup();
            }
        };

        console.log("E3v3seprintjobdetailsViewModel initialized");
    }

    // Register the view model
    OCTOPRINT_VIEWMODELS.push({
        construct: E3v3seprintjobdetailsViewModel,
        dependencies: ["settingsViewModel"]
    });

    console.log("E3v3seprintjobdetailsViewModel registered");
});
