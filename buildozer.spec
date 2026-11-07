[app]
title = Fatelikou
package.name = fatelikou
package.domain = org.fatelikou
source.dir = .
source.include_exts = py,png,jpg,kv,json
source.exclude_dirs = .github, bin, .buildozer, __pycache__
# À augmenter à chaque nouvelle publication (1.0.1, 1.1.0...)
version = 1.0.0
requirements = python3,kivy==2.3.1
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
android.presplash_color = #F5F2E8
orientation = portrait
fullscreen = 0

android.permissions = VIBRATE, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE
android.api = 36
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True
android.release_artifact = aab
android.debug_artifact = apk
p4a.branch = develop
p4a.commit = 1c9a4b4f817847bd8505d972d1a0e6f965929a88

[buildozer]
log_level = 2
warn_on_root = 1
