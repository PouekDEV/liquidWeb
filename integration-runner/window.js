const { app, BrowserWindow } = require("electron");
const { boolean } = require("boolean")
const path = require("node:path")

const width = parseInt(app.commandLine.getSwitchValue("width"));
const height = parseInt(app.commandLine.getSwitchValue("height"));
const url = app.commandLine.getSwitchValue("url");
const configuration = boolean(app.commandLine.getSwitchValue("configuration"));

function createWindow(){
    let win = new BrowserWindow({
        height: height,
        width: width,
        autoHideMenuBar: true,
        webPreferences: {
            devTools: false,
            preload: path.join(__dirname, "nzxt_data_api.js")
        }
    });
    win.loadURL(url + (!configuration ? "?kraken=true" : ""));
}

app.whenReady().then(() => {
    // TODO: Don't create a window for non configuration mode
    createWindow()
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