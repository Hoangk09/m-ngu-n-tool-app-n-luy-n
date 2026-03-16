[app]
title = Quiz Solver
package.name = quizsolver
package.domain = org.nhat

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.include_patterns = *.py,*.json

version = 1.0.4

# Requirements
requirements = python3,kivy,pyjnius,android

orientation = portrait
fullscreen = 0

# Android permissions
android.permissions = INTERNET,SYSTEM_ALERT_WINDOW,BIND_ACCESSIBILITY_SERVICE

# Android API
android.minapi = 24
android.api = 33
android.ndk_api = 24

# Build settings
android.arch = arm64-v8a
android.accept_sdk_license = True

# Add Java source code
android.add_src = java

# Add resources
android.add_resources = res/xml:xml,res/values:values

# Custom AndroidManifest additions
android.manifest_additions = templates/AndroidManifest.tmpl.xml

# Presplash
android.presplash_color = #1a1a2e

# Make package private storage writable
android.private_storage = True

# Gradle dependencies (none needed for accessibility)
# android.gradle_dependencies = 

# Logging
log_level = 2

[buildozer]
log_level = 2
warn_on_root = 1
