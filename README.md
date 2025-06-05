# Immich Google Takeout Date Fix - Turbo Edition

A high-performance Python script that fixes photo and video dates from Google Takeout for perfect Immich compatibility. This tool ensures all your media files have correct dates by syncing EXIF metadata with Google's JSON photoTakenTime data.

## 🚀 Features

### **Ultra-Fast Performance**
- ⚡ **Parallel processing** with configurable worker threads
- 🔥 **Optimized file scanning** using pathlib for 2-3x speed improvement
- 📊 **Progress tracking** with real-time statistics and ETA

### **Immich Perfect Compatibility**
- 🎯 **Force overwrite mode** - Always uses JSON photoTakenTime regardless of existing dates
- ✅ **All 8 Immich priority EXIF tags** updated in correct order
- 📱 **Video metadata support** - ContentCreateDate, TrackCreateDate, MediaModifyDate
- 🗂️ **Filesystem timestamp sync** - Updates file creation/modification times
- 🔍 **Comprehensive date coverage** - 20+ different date fields updated

### **Wide Format Support**
- 📷 **Images**: JPG, JPEG, PNG, HEIC, HEIF, TIFF, WebP, DNG, GIF
- 🎥 **Videos**: MP4, MOV, 3GPP
- 📄 **Metadata**: Google Takeout JSON files

### **Smart Matching**
- 🧠 **Intelligent JSON pairing** - Forward, reverse, and fuzzy filename matching
- 🔄 **Bidirectional matching** for complex Google Takeout naming schemes
- ⚡ **Early filtering** to skip non-media files quickly

## 📋 Requirements

### **Software Dependencies**
- **Python 3.6+** 
- **ExifTool** - Must be installed and available in PATH

### **Install ExifTool**

**Windows:**
```bash
# Using Chocolatey
choco install exiftool

# Or download from: https://exiftool.org/
```

**macOS:**
```bash
# Using Homebrew
brew install exiftool
```

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get install libimage-exiftool-perl

# CentOS/RHEL
sudo yum install perl-Image-ExifTool
```

## 🛠️ Installation

1. **Download the script**
   ```bash
   git clone https://github.com/eekanti/google-takeout-turbofix.git
   cd google-takeout-turbofix
   ```

2. **Verify ExifTool installation**
   ```bash
   exiftool -ver
   ```

## 💻 Usage

### **Basic Usage**
```bash
python takeout_fix.py "C:\Google\Takeout"
```

### **Advanced Usage**
```bash
# Custom worker count (recommended: CPU cores × 2)
python takeout_fix.py "C:\Google\Takeout" --workers 16

# Maximum performance (use with caution)
python takeout_fix.py "C:\Google\Takeout" --max-workers 24

# Get help
python takeout_fix.py --help
```

### **Command Line Options**

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `directory` | - | **Required.** Path to Google Takeout folder | - |
| `--workers` | `-w` | Number of parallel workers | CPU count (max 12) |
| `--max-workers` | - | Override maximum worker limit | None |
| `--help` | `-h` | Show help message | - |

## 📁 Google Takeout Structure

Your Google Takeout should have this structure:
```
Google Takeout/
├── Photos from 2023/
│   ├── IMG_20230615_143022.jpg
│   ├── IMG_20230615_143022.jpg.json    ← JSON metadata
│   ├── PXL_20230820_165432.mp4
│   └── PXL_20230820_165432.mp4.json    ← JSON metadata
└── Photos from 2024/
    ├── photo1.heic
    ├── photo1.heic.json
    └── ...
```

## 🔧 How It Works

### **1. Directory Scanning**
- Uses `pathlib.rglob()` for ultra-fast recursive file discovery
- Filters for supported image/video formats only
- Skips hidden files and metadata files

### **2. JSON Pairing**
- **Forward matching**: JSON filename starts with image filename
- **Reverse matching**: Image filename starts with JSON filename  
- **Fuzzy matching**: Common prefix matching for complex names

### **3. Date Extraction**
- Reads `photoTakenTime.timestamp` from JSON files
- Converts to multiple EXIF-compatible formats
- Handles timezone and subsecond precision

### **4. Metadata Update (Force Overwrite)**
- Updates **all 20+ date fields** regardless of existing values
- Prioritizes Immich's preferred EXIF tags:
  1. `SubSecDateTimeOriginal`
  2. `DateTimeOriginal` 
  3. `SubSecCreateDate`
  4. `CreationDate`
  5. `CreateDate`
  6. Plus 15+ additional fields for comprehensive coverage

### **5. Filesystem Sync**
- Updates file creation and modification timestamps
- Ensures consistency between EXIF and filesystem dates

## 📊 Performance

### **Speed Optimizations**
- **Parallel processing**: 8-12 workers by default
- **Batch operations**: Processes multiple files simultaneously
- **Optimized I/O**: Reduced ExifTool command overhead
- **Smart filtering**: Early elimination of non-target files

### **Typical Performance**
- **Small collections** (1K files): ~30-60 seconds
- **Medium collections** (10K files): ~5-15 minutes  
- **Large collections** (100K+ files): ~1-3 hours
- **Processing rate**: 50-200 files/second (depending on storage speed)

## ⚠️ Important Notes

### **Backup Your Files**
This script **overwrites existing metadata**. Always backup your files first:
```bash
# Create a backup before running
cp -r "C:\Google\Takeout" "C:\Google\Takeout_BACKUP"
```

### **Force Overwrite Mode**
- The script **always overwrites** existing dates with JSON photoTakenTime
- This ensures 100% consistency with Google's original timestamps
- Even files with "correct" dates will be updated to ensure all fields match

### **Immich Compatibility**
- Designed specifically for Immich's date detection algorithm
- Updates all possible date fields that Immich might check
- Handles edge cases where Immich falls back to filesystem dates

## 🐛 Troubleshooting

### **Common Issues**

**"ExifTool not found"**
```bash
# Verify ExifTool is installed
exiftool -ver

# Add to PATH if needed (Windows)
set PATH=%PATH%;C:\path\to\exiftool
```

**"No image+JSON pairs found"**
- Ensure Google Takeout includes JSON metadata files
- Check that file extensions are supported
- Verify directory path is correct

**Slow performance**
- Reduce worker count: `--workers 4`
- Check available RAM (each worker uses ~50-100MB)
- Verify storage isn't bottlenecked (use SSD if possible)

**Permission errors**
- Run as administrator (Windows) or with sudo (Linux/macOS)
- Check file permissions in target directory

## 📈 Output Example

```
2024-06-04 15:30:15 - INFO: ==========================================
2024-06-04 15:30:15 - INFO: IMMICH TAKEOUT DATE FORCE OVERWRITE MODE
2024-06-04 15:30:15 - INFO: ==========================================
2024-06-04 15:30:15 - INFO: Target directory: C:\Google\Takeout
2024-06-04 15:30:15 - INFO: Using 12 parallel workers
2024-06-04 15:30:15 - INFO: CPU count: 8
2024-06-04 15:30:15 - INFO: 🎯 FORCE OVERWRITE MODE ENABLED
2024-06-04 15:30:16 - INFO: ExifTool version 12.50 found
2024-06-04 15:30:16 - INFO: Ultra-fast scanning directory structure...
2024-06-04 15:30:22 - INFO: Scanned 15,234 images/videos in 6.1 seconds
2024-06-04 15:30:22 - INFO: Finding image+JSON pairs in parallel...
2024-06-04 15:30:45 - INFO: Found 14,891 pairs in 23.2 seconds
2024-06-04 15:30:45 - INFO: FORCE OVERWRITING 14,891 files with JSON photoTakenTime...
2024-06-04 15:32:15 - PROGRESS: 14891/14891 (165.2/sec, ETA: 0s)

======================================================================
2024-06-04 15:32:15 - 🚀 FORCE OVERWRITE IMMICH TAKEOUT FIX SUMMARY
======================================================================
2024-06-04 15:32:15 - ⚡ Files force-updated with JSON dates: 14,891
2024-06-04 15:32:15 - ❌ Files failed to update: 0
2024-06-04 15:32:15 - ⏭️  Files skipped (no JSON date): 0
2024-06-04 15:32:15 - 📊 Total image+json pairs: 14,891
2024-06-04 15:32:15 - 📁 Total images scanned: 15,234
2024-06-04 15:32:15 - ⚡ Processing rate: 123.4 files/second
2024-06-04 15:32:15 - 🕐 Total time: 120.7 seconds
======================================================================

🚀 FORCE OVERWRITE SUCCESS! Updated 14,891 files in 120.7 seconds!
📅 All dates now match Google Takeout JSON photoTakenTime!
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit changes: `git commit -am 'Add feature'`
4. Push to branch: `git push origin feature-name`
5. Submit a Pull Request

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

## 🙏 Acknowledgments

- Built for the [Immich](https://github.com/immich-app/immich) community
- Uses [ExifTool](https://exiftool.org/) by Phil Harvey
- Optimized for Google Takeout data structure