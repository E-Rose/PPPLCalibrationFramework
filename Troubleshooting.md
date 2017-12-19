* If the calibration program crashes upon trying to use/load the IR camera:
  * If it gives “OSError: [WinError 193] %1 is not a valid Win32 application”:
    * It might be unable to load “pdvlib.dll” to talk to the cameralink capture card.
      * Check to see if the EDT PDV software is installed. You can also try uninstalling it and reinstalling it.
    * Make sure you are using 64-bit Python; otherwise pdvlib.dll won’t load.
   
* If the calibration program crashed, and now won’t restart (it crashes instead):
  * Try opening Python and importing the thorlabs_apt library.
  * If Python crashes, then it could be that thorlabs_apt wasn’t able to close the USB connections.
    * Power cycle the motion stages. (Open the APT user application, move the stages around, and close the application.)
