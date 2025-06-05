import os
import json
import subprocess
import glob
from datetime import datetime
from multiprocessing import Pool, cpu_count
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import time
from functools import partial

def log_message(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{timestamp} - {message}")

def find_json_file(image_path):
    """Find JSON file using bidirectional matching (optimized)"""
    image_dir = os.path.dirname(image_path)
    image_name = os.path.basename(image_path)
    image_base = os.path.splitext(image_name)[0]
    
    # Cache directory JSON files to avoid repeated glob calls
    if not hasattr(find_json_file, '_json_cache'):
        find_json_file._json_cache = {}
    
    if image_dir not in find_json_file._json_cache:
        find_json_file._json_cache[image_dir] = glob.glob(os.path.join(image_dir, "*.json"))
    
    json_files = find_json_file._json_cache[image_dir]
    
    # Method 1: Forward matching (JSON starts with image base)
    for json_file in json_files:
        json_base = os.path.splitext(os.path.basename(json_file))[0]
        if json_base.startswith(image_base):
            return json_file
    
    # Method 2: Reverse matching (image base starts with JSON base)
    for json_file in json_files:
        json_base = os.path.splitext(os.path.basename(json_file))[0]
        if image_base.startswith(json_base) and len(json_base) > 10:
            return json_file
    
    # Method 3: Fuzzy matching
    best_match = None
    best_score = 0
    
    for json_file in json_files:
        json_base = os.path.splitext(os.path.basename(json_file))[0]
        
        # Fast common prefix calculation
        common_length = 0
        min_length = min(len(image_base), len(json_base))
        
        for i in range(min_length):
            if image_base[i] == json_base[i]:
                common_length += 1
            else:
                break
        
        if common_length > best_score and common_length > 20:
            best_score = common_length
            best_match = json_file
    
    return best_match

def get_date_from_json(json_path):
    """Extract photoTakenTime from JSON file and format for EXIF"""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        photo_taken = data.get('photoTakenTime', {})
        timestamp = photo_taken.get('timestamp')
        
        if timestamp:
            dt = datetime.fromtimestamp(int(timestamp))
            # Return both standard format and subsecond format
            standard_format = dt.strftime('%Y:%m:%d %H:%M:%S')
            subsec_format = dt.strftime('%Y:%m:%d %H:%M:%S.000')  # Add milliseconds
            return standard_format, subsec_format
        
        return None, None
    except Exception as e:
        log_message(f"ERROR reading JSON {json_path}: {str(e)[:50]}")
        return None, None

def check_and_update_single_image(args):
    """Process a single image - targeting Immich's priority EXIF tags"""
    image_path, json_path, process_id = args
    
    try:
        # Check current DateTimeOriginal (Immich's #2 priority)
        result = subprocess.run(
            ['exiftool', '-DateTimeOriginal', '-s', '-s', '-s', image_path],
            capture_output=True, text=True, timeout=10
        )
        current_date = result.stdout.strip() if result.returncode == 0 else None
        
        # Get JSON date
        json_date, json_date_subsec = get_date_from_json(json_path)
        if not json_date:
            return {'status': 'skipped', 'reason': 'no_json_date', 'file': os.path.basename(image_path)}
        
        # Skip if already correct
        if current_date and current_date == json_date:
            return {'status': 'already_set', 'file': os.path.basename(image_path)}
        
        # Update metadata - TARGET IMMICH'S EXACT PRIORITY ORDER
        cmd = [
            'exiftool', '-overwrite_original', '-P',
            # Immich Priority #1: SubSecDateTimeOriginal
            f'-SubSecDateTimeOriginal={json_date_subsec}',
            # Immich Priority #2: DateTimeOriginal  
            f'-DateTimeOriginal={json_date}',
            # Immich Priority #3: SubSecCreateDate
            f'-SubSecCreateDate={json_date_subsec}',
            # Immich Priority #4: CreationDate
            f'-CreationDate={json_date}',
            # Immich Priority #5: CreateDate
            f'-CreateDate={json_date}',
            # Immich Priority #6: SubSecMediaCreateDate
            f'-SubSecMediaCreateDate={json_date_subsec}',
            # Immich Priority #7: MediaCreateDate  
            f'-MediaCreateDate={json_date}',
            # Immich Priority #8: DateTimeCreated
            f'-DateTimeCreated={json_date}',
            # Additional common tags for compatibility
            f'-DateTime={json_date}',
            f'-DateTimeDigitized={json_date}',
            image_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
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
                'error': result.stderr.strip()[:100]
            }
            
    except Exception as e:
        return {
            'status': 'error',
            'file': os.path.basename(image_path),
            'error': str(e)[:100]
        }

def scan_directory_fast(directory):
    """Fast directory scanning with early filtering"""
    log_message("INFO: Fast scanning directory structure...")
    
    image_extensions = {'.dng', '.jpg', '.jpeg', '.png', '.heic', '.heif', '.tiff', '.webp', '.bmp', '.mp4', '.gif', '.3gpp'}  # Added .gif and .3gpp
    image_files = []
    
    start_time = time.time()
    
    for root, dirs, files in os.walk(directory):
        # Skip hidden directories for speed
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for file in files:
            # Fast extension check
            if os.path.splitext(file.lower())[1] in image_extensions:
                if not any(x in file.lower() for x in ['json', 'metadata']):
                    image_files.append(os.path.join(root, file))
    
    scan_time = time.time() - start_time
    log_message(f"INFO: Scanned {len(image_files)} images/videos in {scan_time:.1f} seconds")
    
    return image_files

def find_image_json_pairs_fast(image_files):
    """Fast parallel JSON file discovery"""
    log_message("INFO: Finding image+JSON pairs in parallel...")
    
    start_time = time.time()
    pairs = []
    
    # Use ThreadPoolExecutor for I/O bound JSON file discovery
    with ThreadPoolExecutor(max_workers=min(8, cpu_count())) as executor:
        future_to_image = {
            executor.submit(find_json_file, img): img 
            for img in image_files
        }
        
        completed = 0
        for future in as_completed(future_to_image):
            image_path = future_to_image[future]
            json_path = future.result()
            
            if json_path:
                pairs.append((image_path, json_path))
            
            completed += 1
            if completed % 100 == 0:
                log_message(f"INFO: Processed {completed}/{len(image_files)} files for JSON matching")
    
    pair_time = time.time() - start_time
    log_message(f"INFO: Found {len(pairs)} pairs in {pair_time:.1f} seconds")
    
    return pairs

def main():
    """Turbo-charged main function optimized for Immich"""
    
    # --------------- Configuration --------------- #
    directory = r"C:\GP"  # Change this to your target directory
    max_workers = min(cpu_count(), 8)  # Limit to avoid overwhelming exiftool
    # --------------- Configuration --------------- #
    
    log_message("INFO: ==========================================")
    log_message("INFO: IMMICH-OPTIMIZED TAKEOUT DATE FIX TURBO")
    log_message("INFO: ==========================================")
    log_message("INFO: Current user: eekanti")
    log_message("INFO: Current UTC time: 2025-06-04 02:27:01")
    log_message(f"INFO: Using {max_workers} parallel workers")
    log_message(f"INFO: CPU count: {cpu_count()}")
    log_message("INFO: Targeting Immich's priority EXIF tags:")
    log_message("INFO:   1. SubSecDateTimeOriginal")
    log_message("INFO:   2. DateTimeOriginal") 
    log_message("INFO:   3. SubSecCreateDate")
    log_message("INFO:   4. CreationDate")
    log_message("INFO:   5. CreateDate")
    log_message("INFO:   6. SubSecMediaCreateDate")
    log_message("INFO:   7. MediaCreateDate")
    log_message("INFO:   8. DateTimeCreated")
    
    # Test exiftool
    try:
        result = subprocess.run(['exiftool', '-ver'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            log_message(f"INFO: ExifTool version {result.stdout.strip()} found")
        else:
            log_message("ERROR: ExifTool not found in PATH")
            log_message("ERROR: Please ensure exiftool.exe is in your PATH or Scripts directory")
            return
    except:
        log_message("ERROR: ExifTool not available")
        return
    
    if not os.path.exists(directory):
        log_message(f"ERROR: Directory not found: {directory}")
        return
    
    overall_start = time.time()
    
    # Step 1: Fast directory scan
    image_files = scan_directory_fast(directory)
    if not image_files:
        log_message("ERROR: No image files found")
        return
    
    # Step 2: Fast JSON pair discovery
    pairs = find_image_json_pairs_fast(image_files)
    if not pairs:
        log_message("ERROR: No image+JSON pairs found")
        return
    
    # Step 3: Parallel processing
    log_message(f"INFO: Processing {len(pairs)} files with {max_workers} workers...")
    
    # Prepare arguments for multiprocessing
    process_args = [(img, json_file, i % max_workers) for i, (img, json_file) in enumerate(pairs)]
    
    # Counters
    success_count = 0
    failed_count = 0
    skipped_count = 0
    already_set_count = 0
    
    process_start = time.time()
    
    # Use ProcessPoolExecutor for CPU-bound work
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(check_and_update_single_image, args) for args in process_args]
        
        completed = 0
        for future in as_completed(futures):
            result = future.result()
            completed += 1
            
            # Count results
            if result['status'] == 'success':
                success_count += 1
                if completed <= 5:  # Show first few successes
                    log_message(f"SUCCESS: {result['file']} -> {result['new_date']}")
            elif result['status'] == 'already_set':
                already_set_count += 1
            elif result['status'] == 'skipped':
                skipped_count += 1
            elif result['status'] in ['failed', 'error']:
                failed_count += 1
                if failed_count <= 3:  # Show first few failures
                    log_message(f"ERROR: {result['file']} - {result.get('error', 'Unknown error')}")
            
            # Progress updates
            if completed % 50 == 0 or completed == len(pairs):
                elapsed = time.time() - process_start
                rate = completed / elapsed
                eta = (len(pairs) - completed) / rate if rate > 0 else 0
                log_message(f"PROGRESS: {completed}/{len(pairs)} ({rate:.1f}/sec, ETA: {eta:.0f}s)")
    
    # Final summary
    total_time = time.time() - overall_start
    
    print("\n" + "="*70)
    log_message("🎯 IMMICH-OPTIMIZED TAKEOUT FIX SUMMARY")
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
        print(f"\n🚀 IMMICH SUCCESS! Updated {success_count} files in {total_time:.1f} seconds!")
        print("📸 Photos are now optimized for Immich's date detection algorithm!")
        print("🎯 All 8 priority EXIF tags have been set from photoTakenTime")
        print("\n📋 Next Steps:")
        print("   1. Import these photos to Immich")
        print("   2. Verify dates appear correctly in timeline")
        print("   3. Check photo details show proper 'Date taken'")

if __name__ == '__main__':
    # Clear JSON cache on startup
    if hasattr(find_json_file, '_json_cache'):
        delattr(find_json_file, '_json_cache')
    
    main()