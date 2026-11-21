# Movie Shelf setup

Movie Shelf has two apps. **MovieShelfHost.exe** shares movies stored on a PC. **MovieShelfViewer.exe** shows movies from all the PCs you add. The viewer can also read a folder on its own PC directly.

## Before you start

- Use Windows 10 or 11 on each PC
- Put the PCs on the same trusted home network
- Have at least one MP4, M4V, MKV, or WebM movie in the folder you plan to share
- Copy the ZIP to each PC, right-click it, choose **Extract All**, and keep the extracted folder together

You do not need to install Git, OpenSSL, Python, or a developer tool. You do not need to type terminal commands or move certificate files.

## Share a movie folder from another PC

1. On the PC with the movies, open **MovieShelfHost.exe**
2. Select **Choose folder** and choose the folder containing your movies
3. Leave the first network address selected if it is your home network. The address `127.0.0.1` works only when the viewer is on this same PC
4. Create a password with at least 12 characters and select **Start sharing**
5. Leave the host window open. It shows an address and a pairing code
6. If Windows Firewall asks, allow the host on your **Private** network
7. On the watching PC, open **MovieShelfViewer.exe** and select **Add server**
8. Enter the host's address, pairing code, and password, then select **Add server**

The viewer saves that server for the next time you open it. Start the host app again whenever you want to share from that PC. Repeat these steps for more PCs. Select **Add server** in the viewer whenever you want to add another one.

## Watch movies stored on the viewing PC

Open **MovieShelfViewer.exe**, select **Add local folder**, and choose your movie folder. The viewer reads those files directly. You do not need to run the host app for that folder.

On a new viewer, the Sources page opens until you add a server or local folder. You can mix both kinds of sources. Open **Sources** to add another PC or folder. Use **Remove** beside a source to delete it from the viewer. The page confirms removal, and your movie files stay where they are.

## Everyday use

Use **Discover** for a short poster shelf and **Library** to search every movie. Select a poster to open its separate **Movie player** page, then use the built-in play control. The viewer uses `cover.jpg` beside each movie, or `thumb.jpg` if there is no cover. A movie without either image has a blank poster. If the same movie is on more than one PC, use **Play from** to choose the copy. Use the built-in fullscreen control to expand the video, then press Escape to return. When you pause over or select a movie, the viewer starts preparing it. Select **Refresh** on Discover after changing files. The host must be stopped and started again to notice new, renamed, or removed movies.

If a host is unavailable, its movies will be absent until it is running again. Other sources still work. For a changed host address, remove the old server and add it using the new address and pairing code. Keep the password and pairing code private. The host serves on port 8443 within your network. Router port forwarding is not part of this setup.

The ZIP contains both apps in one folder. Each PC can run either app or both apps. The included host program and certificate helper are started by **MovieShelfHost.exe**. They do not need to be opened directly.
