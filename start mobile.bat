@echo off
setlocal
cd /d "%~dp0\mobile"
echo MystriX Mobile — Expo dev server
if not exist node_modules (
  echo Installing dependencies...
call npm install
)
rem Ensure web dependencies for Expo Web are present
call npx expo install react-native-web react-dom @expo/metro-runtime
call npx expo start
