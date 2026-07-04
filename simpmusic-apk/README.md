# 📱 SimpMusic — APK para Android

`SimpMusic-universal-debug.apk` (~89 MB) es un build **debug universal** del
[fork de SimpMusic de wilwil186](https://github.com/wilwil186/SimpMusic),
compilado en local desde `~/Documentos/SimpMusic`. Funciona en cualquier móvil
Android (arm64, arm32 y x86_64).

Es el «equivalente Android» de [Ritmo](../ritmo/): mismo concepto (YouTube
Music sin anuncios, cuenta de Google, letras, SponsorBlock), pero como app
nativa de Android.

## Instalar

1. Copia el APK al móvil (o descárgalo desde GitHub).
2. Ábrelo y acepta «instalar de orígenes desconocidos».

> Al ser un build **debug** va firmado con la clave de depuración: Android
> mostrará un aviso y no se puede actualizar encima de una instalación firmada
> con la clave de release (desinstala primero la otra si la tienes).

## Recompilar

```bash
cd ~/Documentos/SimpMusic
ANDROID_HOME=$HOME/Android/Sdk ./gradlew :androidApp:assembleDebug
# APKs en androidApp/build/outputs/apk/debug/
```

Para el APK **release firmado** hace falta el keystore (`simpmusic.jks`) y sus
contraseñas:

```bash
KEYSTORE_PASSWORD=… KEY_ALIAS=… KEY_PASSWORD=… ./build_and_sign_apk.sh
```
