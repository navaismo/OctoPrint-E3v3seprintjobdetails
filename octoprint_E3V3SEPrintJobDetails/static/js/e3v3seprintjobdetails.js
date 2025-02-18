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

            if (data.type === "popup") {
                new PNotify({
                    title: 'E3v3seprintjobdetails',
                    text: data.message,
                    type: 'info',
                    hide: true
                });
            } else if (data.type === "close_popup") {
                PNotify.removeAll();
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