@echo off
echo Uploading files to server...
scp server.py root@160.250.136.236:~/quizsolver/
scp templates\admin.html root@160.250.136.236:~/quizsolver/templates/
echo.
echo Restarting server...
ssh root@160.250.136.236 "pkill gunicorn; cd ~/quizsolver && source venv/bin/activate && nohup gunicorn --bind 0.0.0.0:5000 --timeout 120 server:app > /dev/null 2>&1 &"
echo Done!
pause
