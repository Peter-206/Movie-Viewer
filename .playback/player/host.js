"use strict";

// Input: Host markup. Output: Folder picker button. Goal: Let the user choose the library. Description: A native dialog supplies the path.
const folderButton = document.querySelector("#folder");
// Input: Host markup. Output: Selected folder label. Goal: Confirm the library choice. Description: The path is shown only on this PC.
const folderName = document.querySelector("#folder-name");
// Input: Host markup. Output: Address selector. Goal: Show reachable IPv4 addresses. Description: Loopback is available for same-PC testing.
const addressInput = document.querySelector("#address");
// Input: Host markup. Output: Password field. Goal: Authenticate viewers. Description: Cleared after sharing begins.
const passwordInput = document.querySelector("#password");
// Input: Host markup. Output: Setup form. Goal: Start hosting. Description: Native validation checks the password length.
const hostForm = document.querySelector("#host-form");
// Input: Host markup. Output: Setup status. Goal: Explain errors. Description: Safe error text comes from the main process.
const hostStatus = document.querySelector("#host-status");
// Input: Host markup. Output: Sharing section. Goal: Give the viewer pairing details. Description: Hidden until the host is listening.
const sharing = document.querySelector("#sharing");
// Input: Host markup. Output: Stop button. Goal: End sharing. Description: Closing the window also stops the host.
const stopButton = document.querySelector("#stop");
// Input: Folder picker. Output: Chosen path or null. Goal: Keep the selection for Start. Description: Only the main process reads its files.
let selectedFolder = null;

// Input: Native folder picker. Output: Updated form label. Goal: Select movies without a command line. Description: Cancellation preserves the prior folder.
async function chooseFolder() {
  try {
    // Input: Picker action. Output: Folder path or null. Goal: Update the host form. Description: The path stays on this PC.
    const folder = await window.shelfAPI.setup("pick-folder");
    if (folder) { selectedFolder = folder; folderName.textContent = folder; }
  } catch (error) { hostStatus.textContent = error.message; }
}

// Input: Completed host form. Output: Running host state. Goal: Share the selected library. Description: Start is disabled while setup runs.
// event. Input: Submit event. Output: Prevented navigation. Goal: Keep the app on the setup screen. Description: Main-process setup is asynchronous.
async function startSharing(event) {
  event.preventDefault();
  if (!selectedFolder) { hostStatus.textContent = "Choose your movie folder first."; return; }
  hostForm.querySelector("#start").disabled = true;
  hostStatus.textContent = "Starting sharing…";
  try {
    // Input: Form values. Output: Host address and pairing code. Goal: Tell the viewer what to enter. Description: The main process saves the identity.
    const result = await window.shelfAPI.setup("start-host", { folder: selectedFolder, address: addressInput.value, password: passwordInput.value });
    document.querySelector("#share-address").textContent = result.address;
    document.querySelector("#share-code").textContent = result.code;
    passwordInput.value = "";
    sharing.hidden = false;
    hostForm.hidden = true;
    hostStatus.textContent = "Ready for viewers.";
  } catch (error) { hostStatus.textContent = error.message; hostForm.querySelector("#start").disabled = false; }
}

// Input: Stop click. Output: Idle setup form. Goal: End access immediately. Description: The host process is terminated.
async function stopSharing() {
  await window.shelfAPI.setup("stop-host");
  sharing.hidden = true;
  hostForm.hidden = false;
  hostForm.querySelector("#start").disabled = false;
  hostStatus.textContent = "Sharing stopped.";
}

folderButton.addEventListener("click", chooseFolder);
hostForm.addEventListener("submit", startSharing);
stopButton.addEventListener("click", stopSharing);
window.shelfAPI.setup("addresses").then((addresses) => {
  // address. Input: Local interface list. Output: Select option. Goal: Offer the actual host IP. Description: No manual lookup is needed.
  for (const address of addresses) {
    // Input: One IPv4 address. Output: Visible option. Goal: Let the user choose the matching network. Description: Loopback is labeled for this PC only.
    const option = document.createElement("option");
    option.value = address;
    option.textContent = address === "127.0.0.1" ? "127.0.0.1, this PC only" : address;
    addressInput.append(option);
  }
}).catch((error) => { hostStatus.textContent = error.message; });
