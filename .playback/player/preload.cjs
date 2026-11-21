"use strict";

// Input: Electron preload runtime. Output: Restricted renderer bridge. Goal: Keep setup files and passwords outside the web page. Description: Only one named IPC channel is exposed.
const { contextBridge, ipcRenderer } = require("electron");

// Input: Setup action and form data. Output: Main-process result. Goal: Support guided configuration. Description: The main process validates every action.
// action. Input: Renderer request. Output: Allowed action name. Goal: Select setup behavior. Description: No arbitrary IPC channel can be chosen.
// payload. Input: User form. Output: Structured values. Goal: Apply setup. Description: Optional for list and folder actions.
function setup(action, payload) { return ipcRenderer.invoke("shelf:setup", action, payload); }

contextBridge.exposeInMainWorld("shelfAPI", { setup });
