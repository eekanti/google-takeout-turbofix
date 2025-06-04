# Google Takeout Fixer w/ multiprocessing
> Simple script that merges your .json metadata from takeout into your img/video files

**How does it work?**
1. Put all the files into your C:\ dir
2. Open up your windows powershell/cmd
3. Edit script to change the directory section, see below:
\

```py
    # --------------- Configuration --------------- #
    directory = r"C:\Takeout"  # Change this to your target directory
    max_workers = min(cpu_count(), 8)  # Limit to avoid overwhelming exiftool
    # --------------- Configuration --------------- #
```
\
4. Save your change using vscode/notepad++
5. Type command: python takeout_fix_turbo.py in cmd/powershell  

- Script should walk through all your sub directories and apply changes
- Script only updates Date Taken time, which is photoTakenTime in your .json

All credit for **exiftool** goes to https://exiftool.org/


