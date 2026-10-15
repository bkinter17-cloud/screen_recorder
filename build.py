"""
سكربت بناء حزمة التطبيق وملف EXE القابل للتوزيع (Phase 12).

الاستخدام:
    python build.py
    أو عبر البيئة الافتراضية:
    .\\.venv\\Scripts\\python.exe build.py

يُنتج:
    dist/ScreenRecorder/
        ScreenRecorder(.exe)                 (الملف التنفيذي الرئيسي)
        _internal/config/default_config.json (الإعدادات الافتراضية المضمّنة للقراءة فقط)
        _internal/bin/ffmpeg.exe             (إن وُجد في جذر المشروع)
        _internal/bin/ffprobe.exe            (إن وُجد في جذر المشروع لقراءة بيانات التسجيلات)
        ...

ملاحظات معمارية مهمة (خصوصاً عند التثبيت في Program Files):
    1) التطبيق متوافق تماماً مع التثبيت داخل المجلدات المحمية (مثل C:\\Program Files\\Screen Recorder):
       - ملفات إعدادات المستخدم وتعديلاته تُكتب في مجلد المستخدم الخاص:
         %LOCALAPPDATA%\\ScreenRecorder\\user_config.json
       - المجلد الافتراضي لحفظ التسجيلات ولقطات الشاشة يتم توجيهه تلقائياً إلى مجلد المستخدم:
         %USERPROFILE%\\Videos\\ScreenRecorder
       - لا يحاول التطبيق مطلقاً الكتابة أو حفظ الفيديوهات داخل مجلد التشغيل Program Files.
    2) تضمين وتحديد FFmpeg و FFprobe:
       - إذا وُجد ffmpeg.exe (أو ffprobe.exe) في مجلد المشروع، يقوم هذا السكربت بحزمهما
         تلقائياً داخل مجلد bin/ في الحزمة (_internal/bin/).
       - يبحث التطبيق عند الإقلاع أولاً عن المسار المحدد في الإعدادات، ثم عن النسخة
         المضمّنة داخل الحزمة (_internal/bin/)، ثم في PATH النظام.
    3) بعد البناء، يمكن تشغيل installer.iss عبر Inno Setup لإنتاج ملف التثبيت النهائي (Setup EXE).
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
APP_NAME = "ScreenRecorder"
QT_DLL_RUNTIME_HOOK = PROJECT_ROOT / "runtime_hooks" / "qt_dll_path.py"

# Windows terminals may still default to a legacy code page that cannot print
# Arabic status messages. Do not let diagnostic output abort the build.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    print(f"=== بناء {APP_NAME} — النظام الحالي: {platform.system()} ===")

    if platform.system() != "Windows":
        print(
            "تنبيه: أنت لا تُشغّل هذا السكربت على Windows. الناتج سيكون ملفاً "
            "تنفيذياً لنظام هذا الجهاز الحالي فقط، وليس ملف .exe لنظام Windows. "
            "لإنتاج .exe حقيقي، شغّل هذا السكربت على جهاز Windows."
        )

    # تنظيف مخرجات بناء سابقة
    for folder in ("build", "dist"):
        path = PROJECT_ROOT / folder
        if path.exists():
            print(f"جارٍ تنظيف مجلد {folder} السابق...")
            try:
                shutil.rmtree(path)
            except OSError as exc:
                print(f"تحذير: تعذر حذف بعض ملفات {folder} السابقة: {exc}")

    default_config = PROJECT_ROOT / "config" / "default_config.json"
    if not default_config.exists():
        print(f"❌ خطأ: ملف الإعدادات الأساسي غير موجود: {default_config}")
        return 1

    pyinstaller_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--windowed",  # بدون نافذة console خلفية (تطبيق GUI)
        "--noconfirm",
        "--add-data", f"{default_config}{_data_sep()}config",
    ]

    if QT_DLL_RUNTIME_HOOK.is_file():
        pyinstaller_cmd.extend(["--runtime-hook", str(QT_DLL_RUNTIME_HOOK)])

    # تضمين أدوات الوسائط FFmpeg و FFprobe إن توفرت
    ffmpeg_exe = PROJECT_ROOT / "ffmpeg.exe"
    if ffmpeg_exe.is_file():
        pyinstaller_cmd.extend(["--add-binary", f"{ffmpeg_exe}{_data_sep()}bin"])
        print(f"✔ تم تضمين FFmpeg من: {ffmpeg_exe}")
    else:
        print("ℹ لم يُعثر على ffmpeg.exe محلياً — سيعتمد التطبيق على PATH أو إعدادات المستخدم.")

    ffprobe_exe = PROJECT_ROOT / "ffprobe.exe"
    if ffprobe_exe.is_file():
        pyinstaller_cmd.extend(["--add-binary", f"{ffprobe_exe}{_data_sep()}bin"])
        print(f"✔ تم تضمين FFprobe من: {ffprobe_exe}")

    # تضمين أيقونة التطبيق إن توفرت
    for icon_candidate in (
        PROJECT_ROOT / "assets" / "icon.ico",
        PROJECT_ROOT / "assets" / "app.ico",
    ):
        if icon_candidate.is_file():
            pyinstaller_cmd.extend(["--icon", str(icon_candidate)])
            print(f"✔ تم تعيين أيقونة التطبيق: {icon_candidate}")
            break

    # المكتبات التي تُستورد ديناميكياً (لا تظهر لـ PyInstaller تلقائياً عبر static analysis)
    hidden_imports = [
        "soundcard",
        "keyboard",
        "mss",
        "cv2",
    ]
    for mod in hidden_imports:
        pyinstaller_cmd.extend(["--hidden-import", mod])

    pyinstaller_cmd.append(str(PROJECT_ROOT / "main.py"))

    print("\nأمر PyInstaller:")
    print(" ".join(pyinstaller_cmd))
    print("-" * 60)

    result = subprocess.run(pyinstaller_cmd, cwd=PROJECT_ROOT)

    if result.returncode != 0:
        print("❌ فشل البناء.")
        return result.returncode

    dist_folder = PROJECT_ROOT / "dist" / APP_NAME
    print("-" * 60)
    print(f"✅ تم البناء بنجاح: {dist_folder}")
    print("معلومات الحزمة المبنية:")
    print(" • الملف التنفيذي: ScreenRecorder.exe")
    print(" • الإعدادات الافتراضية: _internal/config/default_config.json")
    print(" • حفظ إعدادات المستخدم: يتم تلقائياً في %LOCALAPPDATA%\\ScreenRecorder\\")
    print(" • حفظ تسجيلات المستخدم الافتراضية: يتم تلقائياً في %USERPROFILE%\\Videos\\ScreenRecorder\\")
    print(" • الحزمة جاهزة للتشغيل المباشر أو التغليف بـ Inno Setup (installer.iss).")
    return 0


def _data_sep() -> str:
    """PyInstaller يستخدم ':' على Linux/macOS و ';' على Windows في --add-data."""
    return ";" if platform.system() == "Windows" else ":"


if __name__ == "__main__":
    sys.exit(main())
