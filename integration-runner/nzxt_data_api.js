const { contextBridge } = require("electron");

window.addEventListener("DOMContentLoaded", () => {
    const script = document.createElement("script");
    script.innerHTML = "setInterval(() => { window.nzxt.v1.onMonitoringDataUpdate(nzxtAPI.getData()); }, 1000);";
    document.body.appendChild(script);
});

let data = {};

contextBridge.exposeInMainWorld("nzxtAPI", {
    getData: () => { return data; }
});

setInterval(() => {
    // TODO: Update it with real data from a separate server running on localhost
    let updatedData = {
        cpus: [{
            temperature: Math.floor(Math.random() * 100)
        }],
        gpus: [{},{
            temperature: Math.floor(Math.random() * 100)
        }],
        ram: {
            inUse: Math.floor(Math.random() * 8000),
            totalSize: 8192
        }
    }
    data = updatedData;
}, 1000);