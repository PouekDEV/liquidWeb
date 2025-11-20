const { contextBridge, ipcRenderer } = require("electron");

window.addEventListener("DOMContentLoaded", () => {
    const script = document.createElement("script");
    // With such limited set of devices supported we don't really need to make it any more specific
    script.innerHTML = "setInterval(() => { window.nzxt.v1.width = 640; window.nzxt.v1.height = 640; window.nzxt.v1.shape = 'circle'; window.nzxt.v1.targetFps = " + process.env.framerate + "; window.nzxt.v1.onMonitoringDataUpdate(nzxtAPI.getData()); }, 1000);";
    document.body.appendChild(script);
});

let data = {};

if(process.env.configuration !== false){
    setInterval(async () => {
        data = await ipcRenderer.invoke("data");
    }, 1000);
}

contextBridge.exposeInMainWorld("nzxtAPI", {
    getData: () => { return data; }
});