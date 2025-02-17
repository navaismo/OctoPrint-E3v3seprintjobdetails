// static/js/e3v3seprintjobdetails.js
$(function() {
    function E3v3seprintjobdetailsViewModel(parameters) {
        var self = this;

        // Reference to the print button
        var printButton = $("#job_print");

        // Handle custom messages from the backend
        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin !== "E3v3seprintjobdetails") {
                return;
            }

            if (data.action === "disable_print_button") {
                if (data.status === "start") {
                    // Disable the print button and show loading animation
                    printButton.prop("disabled", true);
                    printButton.html('<i class="fa fa-spinner fa-spin"></i> Loading...');
                } else if (data.status === "end") {
                    // Enable the print button and restore original text
                    printButton.prop("disabled", false);
                    printButton.html('Print');
                }
            }
        };
    }

    // Register the view model
    OCTOPRINT_VIEWMODELS.push({
        construct: E3v3seprintjobdetailsViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#settings_plugin_E3V3SEPrintJobDetails"]
    });
});