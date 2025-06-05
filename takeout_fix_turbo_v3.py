import os
import json
import subprocess
import glob
from datetime import datetime
from multiprocessing import Pool, cpu_count
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import time
from functools import partial
from pathlib import Path  # Add this import

def log_message(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{timestamp} - {message}")

def find_json_file(image_path):
    """Find JSON file using bidirectional matching (optimized with pathlib)"""
    image_dir = Path(image_path).parent
    image_name = Path(image_path).name
    image_base = Path(image_path).stem
    
    # Use pathlib for faster file operations
    json_files = list(image_dir.glob("*.json"))
    
    # Method 1: Forward matching (JSON starts with image base) - FASTEST
    for json_file in json_files:
        if json_file.stem.startswith(image_base):
            return str(json_file)
    
    # Method 2: Reverse matching (image base starts with JSON base)
    for json_file in json_files:
        json_base = json_file.stem
        if image_base.startswith(json_base) and len(json_base) > 10:
            return str(json_file)
    
    # Method 3: Fast fuzzy matching (only if needed)
    best_match = None
    best_score = 0
    
    for json_file in json_files:
        json_base = json_file.stem
        
        # Use set intersection for faster common prefix (only for long names)
        if len(image_base) > 20 and len(json_base) > 20:
            common_length = len(os.path.commonprefix([image_base, json_base]))
            if common_length > best_score and common_length > 20:
                best_score = common_length
                best_match = str(json_file)
    
    return best_match

def get_date_from_json(json_path):
    """Extract photoTakenTime from JSON file and format for EXIF (optimized)"""
    try:
        # Use smaller buffer for faster file reading
        with open(json_path, 'r', encoding='utf-8', buffering=8192) as f:
            data = json.load(f)
        
        # Direct access without .get() for speed
        timestamp = data['photoTakenTime']['timestamp']
        
        if timestamp:
            dt = datetime.fromtimestamp(int(timestamp))
            # Pre-format both strings in one go
            standard_format = dt.strftime('%Y:%m:%d %H:%M:%S')
            subsec_format = f"{standard_format}.000"  # Faster string concatenation
            # ISO format for filesystem timestamps
            iso_format = dt.isoformat()
            return standard_format, subsec_format, dt, iso_format
        
        return None, None, None, None
    except (KeyError, ValueError, TypeError):
        return None, None, None, None
    except Exception as e:
        log_message(f"ERROR reading JSON {json_path}: {str(e)[:50]}")
        return None, None, None, None

def check_and_update_single_image(args):
    """Process a single image - FULL IMMICH COMPATIBILITY"""
    image_path, json_path, process_id = args
    
    try:
        # Get JSON date FIRST (faster than checking current EXIF)
        json_date, json_date_subsec, dt_obj, iso_format = get_date_from_json(json_path)
        if not json_date:
            return {'status': 'skipped', 'reason': 'no_json_date', 'file': os.path.basename(image_path)}
        
        # Only check current date if we have a JSON date
        result = subprocess.run(
            ['exiftool', '-DateTimeOriginal', '-s3', image_path],  # -s3 is faster than -s -s -s
            capture_output=True, text=True, timeout=8, check=False  # Reduced timeout, don't raise on non-zero
        )
        current_date = result.stdout.strip() if result.returncode == 0 else None
        
        # Skip if already correct (exact match)
        if current_date == json_date:
            return {'status': 'already_set', 'file': os.path.basename(image_path)}
        
        # COMPREHENSIVE: Update ALL date fields that Immich might use
        cmd = [
            'exiftool', '-overwrite_original', '-P', '-q',  # Added -q for quiet mode
            
            # === IMMICH'S PRIMARY DATE TAGS (in priority order) ===
            f'-SubSecDateTimeOriginal={json_date_subsec}',     # #1 Priority
            f'-DateTimeOriginal={json_date}',                  # #2 Priority  
            f'-SubSecCreateDate={json_date_subsec}',           # #3 Priority
            f'-CreationDate={json_date}',                      # #4 Priority
            f'-CreateDate={json_date}',                        # #5 Priority
            f'-SubSecMediaCreateDate={json_date_subsec}',      # #6 Priority
            f'-MediaCreateDate={json_date}',                   # #7 Priority
            f'-DateTimeCreated={json_date}',                   # #8 Priority
            
            # === ADDITIONAL COMPREHENSIVE DATE COVERAGE ===
            f'-DateTime={json_date}',                          # General DateTime
            f'-DateTimeDigitized={json_date}',                 # When digitized
            f'-SubSecDateTime={json_date_subsec}',             # SubSec DateTime
            f'-SubSecDateTimeDigitized={json_date_subsec}',    # SubSec Digitized
            
            # === VIDEO-SPECIFIC DATES ===
            f'-ContentCreateDate={json_date}',                 # Video content
            f'-TrackCreateDate={json_date}',                   # Video track
            f'-MediaModifyDate={json_date}',                   # Media modify
            
            # === FILESYSTEM TIMESTAMPS ===
            f'-FileModifyDate={json_date}',                    # File modify date
            f'-FileCreateDate={json_date}',                    # File create date (Windows)
            
            # === ADDITIONAL FALLBACK TAGS ===
            f'-ModifyDate={json_date}',                        # General modify
            f'-MetadataDate={json_date}',                      # Metadata date
            f'-DigitalCreationDate={json_date}',               # Digital creation
            f'-DateCreated={json_date}',                       # Date created
            
            image_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
        
        if result.returncode == 0:
            # BONUS: Also update filesystem timestamps for maximum compatibility
            try:
                file_timestamp = dt_obj.timestamp()
                os.utime(image_path, (file_timestamp, file_timestamp))
            except:
                pass  # Don't fail if filesystem update fails
            
            return {
                'status': 'success', 
                'file': os.path.basename(image_path),
                'old_date': current_date,
                'new_date': json_date,
                'process_id': process_id
            }
        else:
            return {
                'status': 'failed', 
                'file': os.path.basename(image_path),
                'error': result.stderr.strip()[:100] if result.stderr else 'Unknown error'
            }
            
    except Exception as e:
        return {
            'status': 'error',
            'file': os.path.basename(image_path),
            'error': str(e)[:100]
        }

def scan_directory_fast(directory):
    """ULTRA-FAST directory scanning with pathlib"""
    log_message("INFO: Ultra-fast scanning directory structure...")
    
    image_extensions = {'.dng', '.jpg', '.jpeg', '.png', '.heic', '.heif', '.tiff', '.webp', '.bmp', '.mp4', '.gif', '.3gpp'}
    image_files = []
    
    start_time = time.time()
    
    # Use pathlib for much faster directory traversal
    directory_path = Path(directory)
    
    # Single pass with generator expression (much faster)
    for file_path in directory_path.rglob('*'):
        if (file_path.is_file() and 
            file_path.suffix.lower() in image_extensions and
            'json' not in file_path.name.lower() and
            'metadata' not in file_path.name.lower() and
            not file_path.name.startswith('.')):
            image_files.append(str(file_path))
    
    scan_time = time.time() - start_time
    log_message(f"INFO: Scanned {len(image_files)} images/videos in {scan_time:.1f} seconds")
    
    return image_files

def find_image_json_pairs_fast(image_files):
    """OPTIMIZED parallel JSON file discovery"""
    log_message("INFO: Finding image+JSON pairs in parallel...")
    
    start_time = time.time()
    pairs = []
    
    # Increase workers for I/O bound operations
    max_workers = min(16, cpu_count() * 2)  # More aggressive threading for I/O
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks at once (more efficient)
        future_to_image = {
            executor.submit(find_json_file, img): img 
            for img in image_files
        }
        
        completed = 0
        # Process results as they complete
        for future in as_completed(future_to_image):
            image_path = future_to_image[future]
            json_path = future.result()
            
            if json_path:
                pairs.append((image_path, json_path))
            
            completed += 1
            # Reduce progress update frequency for speed
            if completed % 500 == 0:  # Changed from 100 to 500
                log_message(f"INFO: Processed {completed}/{len(image_files)} files for JSON matching")
    
    pair_time = time.time() - start_time
    log_message(f"INFO: Found {len(pairs)} pairs in {pair_time:.1f} seconds")
    
    return pairs

def main():
    """TURBO-OPTIMIZED main function - FULL IMMICH COMPATIBILITY"""
    
    # --------------- Configuration --------------- #
    directory = r"C:\GP"
    max_workers = min(cpu_count(), 12)  # Increased from 8 to 12
    # --------------- Configuration --------------- #
    
    log_message("INFO: ==========================================")
    log_message("INFO: IMMICH-COMPATIBLE TAKEOUT DATE FIX TURBO")
    log_message("INFO: ==========================================")
    log_message(f"INFO: Using {max_workers} parallel workers")
    log_message(f"INFO: CPU count: {cpu_count()}")
    log_message("INFO: 🎯 FULL IMMICH COMPATIBILITY MODE:")
    log_message("INFO:   ✅ All 8 Immich priority EXIF tags")
    log_message("INFO:   ✅ Video-specific metadata tags") 
    log_message("INFO:   ✅ Filesystem timestamps")
    log_message("INFO:   ✅ Comprehensive date field coverage")
    log_message("INFO:   ✅ SubSecond precision support")
    
    # Quick exiftool test
    try:
        result = subprocess.run(['exiftool', '-ver'], capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            log_message(f"INFO: ExifTool version {result.stdout.strip()} found")
        else:
            log_message("ERROR: ExifTool not found")
            return
    except:
        log_message("ERROR: ExifTool not available")
        return
    
    if not os.path.exists(directory):
        log_message(f"ERROR: Directory not found: {directory}")
        return
    
    overall_start = time.time()
    
    # Step 1: Ultra-fast directory scan
    image_files = scan_directory_fast(directory)
    if not image_files:
        log_message("ERROR: No image files found")
        return
    
    # Step 2: Fast JSON pair discovery
    pairs = find_image_json_pairs_fast(image_files)
    if not pairs:
        log_message("ERROR: No image+JSON pairs found")
        return
    
    # Step 3: Optimized parallel processing
    log_message(f"INFO: Processing {len(pairs)} files with {max_workers} workers...")
    
    process_args = [(img, json_file, i % max_workers) for i, (img, json_file) in enumerate(pairs)]
    
    success_count = 0
    failed_count = 0
    skipped_count = 0
    already_set_count = 0
    
    process_start = time.time()
    
    # Optimized ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(check_and_update_single_image, args) for args in process_args]
        
        completed = 0
        for future in as_completed(futures):
            result = future.result()
            completed += 1
            
            # Count results
            if result['status'] == 'success':
                success_count += 1
                if completed <= 3:  # Show fewer successes for speed
                    log_message(f"SUCCESS: {result['file']} -> {result['new_date']}")
            elif result['status'] == 'already_set':
                already_set_count += 1
            elif result['status'] == 'skipped':
                skipped_count += 1
            elif result['status'] in ['failed', 'error']:
                failed_count += 1
                if failed_count <= 2:  # Show fewer failures for speed
                    log_message(f"ERROR: {result['file']} - {result.get('error', 'Unknown error')}")
            
            # Less frequent progress updates
            if completed % 100 == 0 or completed == len(pairs):
                elapsed = time.time() - process_start
                rate = completed / elapsed
                eta = (len(pairs) - completed) / rate if rate > 0 else 0
                log_message(f"PROGRESS: {completed}/{len(pairs)} ({rate:.1f}/sec, ETA: {eta:.0f}s)")
    
    # Final summary
    total_time = time.time() - overall_start
    
    print("\n" + "="*70)
    log_message("🚀 ULTRA-FAST IMMICH TAKEOUT FIX SUMMARY")
    print("="*70)
    log_message(f"✅ Files updated successfully: {success_count}")
    log_message(f"🔄 Files already correctly set: {already_set_count}")
    log_message(f"❌ Files failed to update: {failed_count}")
    log_message(f"⏭️  Files skipped (no JSON date): {skipped_count}")
    log_message(f"📊 Total image+json pairs: {len(pairs)}")
    log_message(f"📁 Total images scanned: {len(image_files)}")
    log_message(f"⚡ Processing rate: {len(pairs)/total_time:.1f} files/second")
    log_message(f"🕐 Total time: {total_time:.1f} seconds")
    print("="*70)
    
    if success_count > 0:
        print(f"\n🚀 ULTRA-FAST SUCCESS! Updated {success_count} files in {total_time:.1f} seconds!")

if __name__ == '__main__':
    main()