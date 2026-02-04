 #Comando no nuitka

 
python3 -m nuitka --onefile --enable-plugin=pyside6 --include-qt-plugins=sensible,platforminputcontexts --output-dir=build -o GCL.bin main.py