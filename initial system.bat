@echo off
REM ✅ Activate Anaconda base environment
CALL "%USERPROFILE%\miniconda3\Scripts\activate.bat"

REM ✅ Activate conda environment
call conda activate hobby

REM ✅ Set environment variables for Django superuser
set DJANGO_SUPERUSER_USERNAME=admin
set DJANGO_SUPERUSER_EMAIL=admin@dummy.com
set DJANGO_SUPERUSER_PASSWORD=123

REM ✅ Delete db.sqlite3
del db.sqlite3

REM ✅ Run createsuperuser without prompts
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser --noinput

REM ✅ Optional: pause so you can see output
pause