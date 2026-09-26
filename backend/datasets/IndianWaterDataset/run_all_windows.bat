@echo off
echo Installing required Python packages...
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo STEP 1: Scraping images...
python scrape_indian_water.py
if errorlevel 1 goto :error

echo.
echo STEP 2: Cleaning duplicates...
python clean_dataset.py
if errorlevel 1 goto :error

echo.
echo STEP 3: Building 200-image candidate set...
python make_test_set.py
if errorlevel 1 goto :error

echo.
echo COMPLETE.
echo Please manually review the 200-image folder before submission.
pause
exit /b 0

:error
echo.
echo Something failed. Read the error above.
pause
exit /b 1
