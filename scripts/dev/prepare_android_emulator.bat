@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem Makolo Android emulator startup from PowerShell (Windows).
rem Never wipe emulator data or terminate unrelated Android devices.
set "MAKOLO_AVD=Makolo_API_35"
set "MAKOLO_DEVICE=emulator-5554"

where adb >nul 2>&1
if errorlevel 1 (
  echo [Makolo] Android SDK adb is not on PATH.
  exit /b 1
)
echo [Makolo] Checking Android emulator...
adb start-server >nul 2>&1
call :read_state

rem When Android is already ready, do not relaunch or disturb it.
if /i "!MAKOLO_STATE!"=="device" (
  call :check_boot
  if "!MAKOLO_BOOT!"=="1" goto :ready
)

if /i "!MAKOLO_STATE!"=="absent" (
  where flutter >nul 2>&1
  if errorlevel 1 (
    echo [Makolo] Flutter is not on PATH.
    exit /b 1
  )
  echo [Makolo] Starting !MAKOLO_AVD!...
  flutter emulators --launch "!MAKOLO_AVD!"
  if errorlevel 1 (
    echo [Makolo] Could not launch !MAKOLO_AVD!.
    exit /b 1
  )
)

rem Wait for Android boot without restarting adb.
rem Restarting adb can invalidate VS Code / Flutter device sessions.
set "MAKOLO_OFFLINE_CHECKS=0"
for /L %%I in (1,1,120) do (
  call :read_state
  if /i "!MAKOLO_STATE!"=="device" (
    call :check_boot
    if "!MAKOLO_BOOT!"=="1" goto :ready
  )
  if /i "!MAKOLO_STATE!"=="offline" (
    set /a MAKOLO_OFFLINE_CHECKS+=1 >nul
    if !MAKOLO_OFFLINE_CHECKS! GEQ 20 (
      echo [Makolo] Emulator is stuck offline; adb will not be restarted automatically.
      echo [Makolo] Close the stale emulator session before starting a new one.
      echo [Makolo] Check: adb devices
      exit /b 1
    )
  ) else (
    set "MAKOLO_OFFLINE_CHECKS=0"
  )
  if %%I EQU 1 echo [Makolo] Waiting for Android to boot...
  if %%I EQU 60 echo [Makolo] Still waiting: !MAKOLO_STATE!.
  ping -n 3 127.0.0.1 >nul
)

echo [Makolo] Emulator did not become ready: !MAKOLO_STATE!.
echo [Makolo] Check the emulator window and adb devices; do not start a second copy.
exit /b 1

:ready
echo [Makolo] Emulator ready: !MAKOLO_DEVICE!.
exit /b 0

:check_boot
set "MAKOLO_BOOT="
for /f "tokens=*" %%B in ('adb -s !MAKOLO_DEVICE! shell getprop sys.boot_completed 2^>nul') do set "MAKOLO_BOOT=%%B"
exit /b 0

:read_state
set "MAKOLO_STATE=absent"
for /f "tokens=1,2" %%A in ('adb devices 2^>nul') do (
  if /i "%%A"=="!MAKOLO_DEVICE!" set "MAKOLO_STATE=%%B"
)
exit /b 0
