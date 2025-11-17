import subprocess, sys, os, shutil

def main():
    qrc = "resources.qrc"
    out = "resources_rc.py"

    pyrcc_exe = r"C:\Program Files\QGIS 3.30.3\apps\Python39\Scripts\pyrcc5.exe"
    qgis_python = r"C:\Program Files\QGIS 3.30.3\bin\python-qgis.bat"

    if not os.path.exists(qrc):
        print(f"❌ {qrc} not found")
        sys.exit(1)

    print(f"⚙️ Compiling {qrc} → {out}")

    try:
        # First try pyrcc5.exe directly
        subprocess.check_call([pyrcc_exe, qrc, "-o", out])
        print("✅ Done with pyrcc5.exe")
    except Exception as e:
        print(f"⚠️ pyrcc5.exe failed: {e}")
        print("🔄 Trying fallback using python-qgis.bat …")

        try:
            subprocess.check_call(
                [qgis_python, "-m", "PyQt5.pyrcc_main", qrc, "-o", out]
            )
            print("✅ Done with python-qgis.bat fallback")
        except Exception as e2:
            print(f"❌ Both methods failed: {e2}")
            sys.exit(1)

if __name__ == "__main__":
    main()
