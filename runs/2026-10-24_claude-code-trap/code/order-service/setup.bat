@echo off
cd /d "%~dp0"
git init -q
git add -A
git rm --cached -q setup.bat
git commit -q -m "v2 migration in progress"
del "%~f0"
