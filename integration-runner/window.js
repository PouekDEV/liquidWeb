const { app, BrowserWindow, ipcMain } = require("electron");
const { exit } = require("node:process");
const path = require("node:path");
const WebSocket = require("ws");

if(!app.commandLine.hasSwitch("configuration") || !app.commandLine.hasSwitch("width") || !app.commandLine.hasSwitch("height") || !app.commandLine.hasSwitch("fps") || !app.commandLine.hasSwitch("url")){
    console.log("[INTEGRATION-RUNNER] Width, height, url, configuration and fps values must be provided");
    exit(0);
}

const width = parseInt(app.commandLine.getSwitchValue("width"));
const height = parseInt(app.commandLine.getSwitchValue("height"));
let framerate = parseInt(app.commandLine.getSwitchValue("fps"));
const url = app.commandLine.getSwitchValue("url");
const configuration = boolean(app.commandLine.getSwitchValue("configuration"));
let PORT = undefined;

if(!configuration && !app.commandLine.hasSwitch("port")){
    console.log("[INTEGRATION-RUNNER] Port hasn't been provided");
    exit(0);
}
else{
    PORT = parseInt(app.commandLine.getSwitchValue("port"));
}

if(framerate > 30 && !configuration){
    console.log("[INTEGRATION-RUNNER] Maximum supported framerate is 30 fps.");
    framerate = 30;
}
console.log("[INTEGRATION-RUNNER] Initiating with", width, "px width,", height, "px height,", framerate, "fps and in", (configuration ? "configuration" : "normal"), "mode with url:", url, "using ports:", PORT, "and", PORT + 1);
// Easy way to pass a value to the preload script that is only needed once
process.env.framerate = framerate;
process.env.configuration = configuration;
process.env.width = width;
process.env.height = height;

let hardwareData = {};
ipcMain.handle("data", () => hardwareData);

if(!configuration){
    app.commandLine.appendSwitch("high-dpi-support", "1");
    app.commandLine.appendSwitch("force-device-scale-factor", "1");
    setTimeout(fetchHardwareInfo, 5000);
}

function fetchHardwareInfo(){
    fetch(`http://localhost:${PORT + 1}`)
    .then(response => response.json())
    .then(data => {
        hardwareData = data;
        setTimeout(fetchHardwareInfo, 1000);
    })
    .catch(err => {
            console.error("[INTEGRATION-RUNNER] Error while fetching hardware info. Retrying in 5 seconds...");
            setTimeout(fetchHardwareInfo, 5000);
        }
    );
}

function boolean(value){
    switch (Object.prototype.toString.call(value)) {
        case '[object String]':
            return [ 'true', 't', 'yes', 'y', 'on', '1' ].includes(value.trim().toLowerCase());
        case '[object Number]':
            return value.valueOf() === 1;
        case '[object Boolean]':
            return value.valueOf();
        default:
            return false;
    }
};

function createWS(url){
    let ws;
    function connect(){
        ws = new WebSocket(url);
        ws.on("open", () => {
            console.log("[INTEGRATION-RUNNER] Connected to frame receiver");
        });
        ws.on("close", () => {
            console.log("[INTEGRATION-RUNNER] Server closed. Retrying in 5 seconds...");
            setTimeout(connect, 5000);
        });
        ws.on("error", (err) => {
            // Filter out the AggregateErrors that are from the lack of response from the server when it's down or not started yet
            if(err?.errors.length != 2 && ws.readyState !== WebSocket.CLOSED){
                console.error("[INTEGRATION-RUNNER] Server error:", err);
            }
            ws.close();
        });
    }
    connect();
    return{
        send: (data) => {
            if(ws && ws.readyState === WebSocket.OPEN){
                ws.send(data);
            }
        },
    };
}

function createWindow(){
    let win = new BrowserWindow({
        height: height,
        width: width,
        autoHideMenuBar: true,
        show: configuration,
        webPreferences: {
            devTools: false,
            offscreen: !configuration,
            preload: path.join(__dirname, "nzxt_data_api.js")
        }
    });
    win.loadURL(url + (!configuration ? "?kraken=true" : ""));
    if(!configuration){
        setTimeout(() => {
            let ws = createWS(`ws://localhost:${PORT}`);
            win.webContents.on("paint", (_event, _dirty, image) => {
                if(ws && ws.send){
                    ws.send(image.toJPEG(70));
                }
            });
        }, 5000);
        win.webContents.setFrameRate(framerate);
    }
    win.setMenuBarVisibility(false);
}

app.whenReady().then(() => {
    createWindow();
    app.on("activate", () => {
        if(BrowserWindow.getAllWindows().length === 0){
            createWindow();
        }
    });
});

app.on("window-all-closed", () => {
    if(process.platform !== "darwin"){
        app.quit();
    }
});