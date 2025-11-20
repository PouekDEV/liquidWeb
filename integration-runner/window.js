const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("node:path");
const WebSocket = require("ws");

const width = parseInt(app.commandLine.getSwitchValue("width"));
const height = parseInt(app.commandLine.getSwitchValue("height"));
let framerate = parseInt(app.commandLine.getSwitchValue("fps"));
const url = app.commandLine.getSwitchValue("url");
const configuration = boolean(app.commandLine.getSwitchValue("configuration"));

if(framerate > 35 && !configuration){
    console.log("Maximum supported framerate is 35 fps.");
    framerate = 35;
}
console.log("Initiating with", width, "px width,", height, "px height,", framerate, "fps and in", (configuration ? "configuration" : "normal"), "mode with url:", url);
// Easy way to pass a value to the preload script that is only needed once
process.env.framerate = framerate;
process.env.configuration = configuration;

let hardwareData = {};

if(!configuration){
    app.commandLine.appendSwitch("high-dpi-support", "1");
    app.commandLine.appendSwitch("force-device-scale-factor", "1");
    setInterval(() => {
        fetch("http://localhost:54218")
        .then(response => response.json())
        .then(data => {
            hardwareData = data;
        })
        .catch(err => console.error("Error while getting hardware info:", err));
    }, 1000);
    ipcMain.handle("data", () => hardwareData);
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
            console.log("Connected to the frame writing server");
        });
        ws.on("close", () => {
            console.log("Server closed. Retrying in 5 seconds...");
            setTimeout(connect, 5000);
        });
        ws.on("error", (err) => {
            // Filter out the AggregateErrors that are from the lack of response from the server when it's down or not started yet
            if(err?.errors.length != 2 && ws.readyState !== WebSocket.CLOSED){
                console.error("Server error:", err);
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
        let ws = createWS("ws://localhost:54217");
        win.webContents.on("paint", (_event, _dirty, image) => {
            if(ws && ws.send){
                ws.send(image.toPNG());
            }
        });
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