
@echo off
echo Closing running Chrome instances...
taskkill /F /IM chrome.exe /T >nul 2>&1

echo Starting Chrome in Debug Mode...
echo Please log in to onluyen.vn in the opened window.
echo LEAVE THIS WINDOW OPEN.
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\selenium\ChromeProfile"
pause
