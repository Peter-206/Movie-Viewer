# Third-party notices

Source releases do not bundle Python or dependency packages. Install dependencies from their upstream distributions and retain their included notices when redistributing them.

| Component | Role | Upstream license information |
| --- | --- | --- |
| Python and Tkinter | Runtime and GUI | [Python license](https://docs.python.org/3/license.html) |
| Tcl/Tk | GUI runtime included with Windows Python | [Tcl/Tk license](https://www.tcl.tk/software/tcltk/license.html) |
| Pillow | Images | [Pillow license](https://github.com/python-pillow/Pillow/blob/main/LICENSE) |
| PyInstaller | Optional executable builder | [PyInstaller license and bootloader exception](https://pyinstaller.org/en/stable/license.html) |
| psutil | Package verification only | [psutil license](https://github.com/giampaolo/psutil/blob/master/LICENSE) |

These links identify upstream projects. They do not replace required license texts. Before publishing a bundled executable, inventory the actual bundle, include the applicable full license texts for its runtime, libraries and transitive components, and review their redistribution requirements. The source-release workflow deliberately does not publish an executable.
