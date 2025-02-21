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

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            console.log(">>> Received plugin message from:", plugin, "Data:", data);
            if (plugin !== "E3V3SEPrintJobDetails") return;

            if (data.type === "popup") {
                console.log(">>> Showing popup with message:", data.message);
                showPopup(data.message);
            } else if (data.type === "close_popup") {
                closePopup();
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
