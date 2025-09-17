@echo off
REM ✅ Activate Anaconda base environment
CALL "%USERPROFILE%\miniconda3\Scripts\activate.bat"

REM ✅ Activate conda environment
call conda activate hobby

REM ✅ Run createsuperuser without prompts
python base64converter.py

REM ✅ Optional: pause so you can see output
pause