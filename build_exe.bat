@echo off
echo ==========================================
echo Quiz Solver - Build EXE
echo ==========================================

echo.
echo [1/2] Installing dependencies...
pip install pyinstaller pillow google-generativeai undetected-chromedriver selenium requests

echo.
echo [2/2] Building EXE...
pyinstaller --onefile --windowed --name "QuizSolver" --icon=NONE quiz_solver_app.py

echo.
echo ==========================================
echo Build complete! 
echo EXE file: dist\QuizSolver.exe
echo ==========================================
pause
