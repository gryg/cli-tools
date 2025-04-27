#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import argparse
import fnmatch # For more flexible pattern matching (optional enhancement shown)

# --- Configuration ---
# You can add more extensions likely to be text-based if needed,
# but the primary check is trying to decode as UTF-8.
# TEXT_EXTENSIONS = {'.txt', '.py', '.js', '.java', '.c', '.cpp', '.h', '.hpp',
#                    '.md', '.json', '.yaml', '.yml', '.xml', '.html', '.css',
#                    '.sh', '.bat', '.ps1', '.rb', '.php', '.go', '.rs', '.swift',
#                    '.kt', '.kts', '.scala', '.pl', '.pm', '.lua', '.r', '.dart',
#                    '.dockerfile', 'Dockerfile', '.gitignore', '.gitattributes',
#                    '.env', '.config', '.conf', '.ini', '.toml', '.cfg'}
# Using UTF-8 decoding check is generally more robust than relying solely on extensions.


# --- Helper Functions ---
def is_likely_text_file(file_path):
    """
    Attempts to read a small portion of the file to determine if it's likely text.
    Primarily checks if the content can be decoded as UTF-8.
    """
    try:
        # Check if file is empty first
        if os.path.getsize(file_path) == 0:
            return True # Treat empty files as text
        # Check if it's a regular file and not a symlink etc. that might cause issues
        if not os.path.isfile(file_path):
             # print(f"Skipping non-regular file: {file_path}")
             return False
        with open(file_path, 'r', encoding='utf-8', errors='strict') as f:
            f.read(1024) # Try reading a small chunk
        return True
    except UnicodeDecodeError:
        # print(f"Skipping binary file (UnicodeDecodeError): {file_path}")
        return False
    except OSError as e: # Handle cases like permission errors or special files
         # print(f"Skipping non-regular or inaccessible file {file_path}: {e}")
         return False
    except Exception as e:
        # Handle other potential errors like permission issues during read
        print(f"Warning: Could not read file {file_path}. Error: {e}")
        return False

def parse_pattern_file(filepath):
    """
    Reads a file containing patterns (like .gitignore), ignoring comments and empty lines.
    Returns a list of patterns.
    """
    patterns = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                stripped_line = line.strip()
                if stripped_line and not stripped_line.startswith('#'):
                    patterns.append(stripped_line)
    except FileNotFoundError:
        print(f"Warning: Pattern file not found: {filepath}")
    except Exception as e:
        print(f"Warning: Error reading pattern file {filepath}: {e}")
    return patterns

def normalize_path(path):
    """Normalizes path separators to forward slashes for consistent matching."""
    return path.replace(os.sep, '/')

# --- Main Logic ---

def create_summary(output_filename, start_dir='.',
                   include_dirs=None, include_files=None, include_patterns=None,
                   exclude_dirs=None, exclude_files=None, exclude_patterns=None,
                   inclusion_mode=False):
    """
    Walks the directory tree, reads text files based on include/exclude rules,
    and writes their content to the output file, separated by headers.

    Args:
        output_filename (str): The name of the summary file to create.
        start_dir (str): The root directory to start scanning.
        include_dirs (set): Set of normalized directory paths to include directly.
        include_files (set): Set of normalized file paths/names to include directly.
        include_patterns (list): List of fnmatch patterns from include file.
        exclude_dirs (set): Set of normalized directory paths to exclude directly.
        exclude_files (set): Set of normalized file paths/names to exclude directly.
        exclude_patterns (list): List of fnmatch patterns (from file + CLI excludes).
        inclusion_mode (bool): True if any include flag was specified by the user.
    """
    # Ensure inputs are sets/lists to avoid None checks later
    include_dirs = include_dirs or set()
    include_files = include_files or set()
    include_patterns = include_patterns or []
    exclude_dirs = exclude_dirs or set()
    exclude_files = exclude_files or set()
    exclude_patterns = exclude_patterns or [] # Combined CLI and file patterns

    # --- Prepare combined exclusion patterns (CLI + File) ---
    # Add direct file/dir exclusions to the pattern list for comprehensive fnmatch checks
    # Note: Direct checks are still performed first for efficiency where applicable
    combined_exclude_patterns = list(exclude_patterns) # Start with patterns from file
    combined_exclude_patterns.extend(exclude_files) # Add direct files
    combined_exclude_patterns.extend([d + '/' if not d.endswith('/') else d for d in exclude_dirs]) # Add direct dirs

    # Always exclude the summary file itself
    summary_file_norm = normalize_path(os.path.normpath(os.path.join(start_dir, output_filename)))
    exclude_files.add(summary_file_norm)
    if summary_file_norm not in combined_exclude_patterns:
         combined_exclude_patterns.append(summary_file_norm)

    # --- Logging ---
    skipped_dirs_count = 0
    skipped_files_count = 0
    processed_files_count = 0
    considered_by_include_count = 0
    excluded_count = 0

    print(f"Starting summary creation. Output file: {output_filename}")
    if inclusion_mode:
        print("Inclusion Mode ACTIVE (only specified items will be considered)")
        if include_dirs: print(f"Including directories: {include_dirs}")
        if include_files: print(f"Including files: {include_files}")
        if include_patterns: print(f"Including paths matching patterns: {include_patterns}")
    else:
        print("Inclusion Mode OFF (all items considered by default)")

    print("--- Exclusions ---")
    if exclude_dirs: print(f"Excluding directories directly: {exclude_dirs}")
    if exclude_files: print(f"Excluding files directly: {exclude_files}")
    if exclude_patterns: print(f"Excluding paths matching patterns from file: {exclude_patterns}") # Original file patterns
    print(f"(Effective exclude patterns including direct rules: {combined_exclude_patterns})") # All patterns
    print("-" * 20)

    # --- File Processing ---
    try:
        with open(os.path.join(start_dir, output_filename), 'w', encoding='utf-8') as outfile:
            # os.walk iterates through directory tree top-down
            for dirpath, dirnames, filenames in os.walk(start_dir, topdown=True):

                current_dir_abs = os.path.normpath(dirpath)
                current_dir_rel = normalize_path(os.path.relpath(current_dir_abs, start_dir))
                # Handle root case where relative path is '.'
                if current_dir_rel == '.':
                    current_dir_rel = '' # Use empty string for root checks below

                # --- Directory Exclusion (applied before descending) ---
                dirs_to_remove = set()
                original_dirnames = list(dirnames) # Copy for iteration

                for dirname in original_dirnames:
                    sub_dir_abs = os.path.normpath(os.path.join(dirpath, dirname))
                    sub_dir_rel = normalize_path(os.path.relpath(sub_dir_abs, start_dir))
                    sub_dir_rel_with_slash = sub_dir_rel + '/'

                    is_excluded = False
                    if sub_dir_rel in exclude_dirs: # Direct dir path match
                        is_excluded = True
                    else:
                        # Check pattern exclusion
                        for pattern in combined_exclude_patterns:
                            if fnmatch.fnmatch(sub_dir_rel_with_slash, pattern) or \
                               fnmatch.fnmatch(sub_dir_rel, pattern) or \
                               fnmatch.fnmatch(dirname, pattern.rstrip('/')):
                                is_excluded = True
                                break

                    if is_excluded:
                        # print(f"Excluding directory tree: {sub_dir_rel}")
                        dirs_to_remove.add(dirname)
                        skipped_dirs_count += 1

                # Remove excluded directories efficiently
                dirnames[:] = [d for d in dirnames if d not in dirs_to_remove]

                # --- File Processing and Filtering ---
                for filename in filenames:
                    file_abs_path = os.path.normpath(os.path.join(dirpath, filename))
                    file_rel_path = normalize_path(os.path.relpath(file_abs_path, start_dir))

                    # --- Step 1: Inclusion Check (only if inclusion_mode is ON) ---
                    if inclusion_mode:
                        should_consider = False
                        # Check direct file include
                        if file_rel_path in include_files or filename in include_files:
                            should_consider = True
                        # Check if file is within an included directory
                        if not should_consider:
                            for inc_dir in include_dirs:
                                # Check if file path starts with included dir path
                                # Add '/' to avoid partial matches (e.g., 'src-data' matching 'src')
                                if file_rel_path.startswith(inc_dir + '/'):
                                    should_consider = True
                                    break
                        # Check pattern include
                        if not should_consider:
                            for pattern in include_patterns:
                                if fnmatch.fnmatch(file_rel_path, pattern) or fnmatch.fnmatch(filename, pattern):
                                    should_consider = True
                                    break

                        if not should_consider:
                            # If inclusion mode is on, but this file doesn't match any rule, skip.
                            skipped_files_count += 1
                            continue
                        else:
                            considered_by_include_count += 1

                    # --- Step 2: Exclusion Check (Always applied) ---
                    is_excluded = False
                    # Direct file exclude check
                    if file_rel_path in exclude_files or filename in exclude_files:
                        is_excluded = True
                    else:
                        # Pattern exclude check
                        for pattern in combined_exclude_patterns:
                            if fnmatch.fnmatch(file_rel_path, pattern) or fnmatch.fnmatch(filename, pattern):
                                is_excluded = True
                                break

                    if is_excluded:
                        excluded_count += 1
                        skipped_files_count += 1
                        continue

                    # --- Step 3: Text File Check and Content Addition ---
                    if is_likely_text_file(file_abs_path):
                        # print(f"Adding: {file_rel_path}")
                        try:
                            # Ensure we are reading from the absolute path
                            with open(file_abs_path, 'r', encoding='utf-8', errors='ignore') as infile:
                                content = infile.read()

                            # Write header (using normalized relative path)
                            outfile.write(f"# {file_rel_path}\n")
                            outfile.write(content)
                            outfile.write("\n\n") # Add two newlines for separation
                            processed_files_count += 1
                        except Exception as e:
                            print(f"Error reading or writing file {file_rel_path}: {e}")
                            skipped_files_count += 1
                    else:
                         # print(f"Skipping binary/unreadable file: {file_rel_path}")
                         skipped_files_count += 1

    except IOError as e:
        print(f"Error opening or writing summary file {output_filename}: {e}")
        return # Exit if we can't write the main file

    print("-" * 20)
    print(f"Summary creation complete: {output_filename}")
    print(f"Processed {processed_files_count} text files.")
    if inclusion_mode:
         print(f"Considered {considered_by_include_count} files based on inclusion rules.")
    print(f"Skipped {skipped_files_count} files (excluded, non-matching include, binary, or errors).")
    if excluded_count > 0:
        print(f"({excluded_count} files matched exclude rules/patterns).")
    if skipped_dirs_count > 0:
      print(f"Skipped descending into {skipped_dirs_count} excluded directory trees.")


# --- Script Execution Entry Point ---

def cli_entry_point():
    """
    Parses command-line arguments and initiates the summary creation process.
    """
    parser = argparse.ArgumentParser(
        description="Summarize text files in a directory tree into a single file, with options for inclusion and exclusion.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Inclusion/Exclusion Logic:
  - If NO --include flags (--include-dirs, --include-files, --include-from) are used,
    all files under the current path are considered by default.
  - If ANY --include flag IS used, only files/directories matching at least one
    inclusion rule are considered.
  - Exclusion flags/files (--exclude-*) are always applied last. A file must pass
    inclusion checks (if active) AND NOT match any exclusion rule to be added.

Pattern files (for --include-from/--exclude-from) use .gitignore-like syntax:
  - Each line is a pattern (# lines and blank lines ignored).
  - Patterns match paths relative to the starting directory (use '/').
  - Wildcards (*, ?, [seq]) work. '/' at end matches directories.

Examples:
  pathsum                   # Default: Include everything (except summary file)
  pathsum --exclude-dirs node_modules build .git venv # Exclude common dirs
  pathsum --exclude-from .gitignore                  # Use .gitignore for exclusions
  pathsum --include-dirs src tests --include-files config.yaml # Only include these
  pathsum --include-from .pathsuminclude --exclude-from .gitignore # Combine rules
"""
    )

    # Inclusion Arguments
    parser.add_argument(
        "--include-dirs",
        nargs='+',
        metavar='DIR',
        default=[],
        help="Space-separated list of directory paths to include. Activates inclusion mode."
    )
    parser.add_argument(
        "--include-files",
        nargs='+',
        metavar='FILE',
        default=[],
        help="Space-separated list of file names or paths to include. Activates inclusion mode."
    )
    parser.add_argument(
        "--include-from",
        metavar='FILE',
        help="Specify a file containing patterns. ONLY items matching these patterns will be included. Activates inclusion mode."
    )

    # Exclusion Arguments
    parser.add_argument(
        "--exclude-dirs",
        nargs='+',
        metavar='DIR',
        default=[],
        help="Space-separated list of directory paths to exclude directly."
    )
    parser.add_argument(
        "--exclude-files",
        nargs='+',
        metavar='FILE',
        default=[],
        help="Space-separated list of file names or paths to exclude directly."
    )
    parser.add_argument(
        "--exclude-from",
        metavar='FILE',
        help="Specify a file containing patterns of files/directories to exclude (like .gitignore)."
    )

    args = parser.parse_args()

    # --- Determine if Inclusion Mode is Active ---
    inclusion_mode_active = bool(args.include_dirs or args.include_files or args.include_from)

    # --- Process patterns from files ---
    include_patterns_from_file = []
    if args.include_from:
        include_patterns_from_file = parse_pattern_file(args.include_from)
        if not include_patterns_from_file and not args.include_dirs and not args.include_files:
             print(f"Warning: Include file '{args.include_from}' was empty or not found, and no other --include flags used. No files will be included.")
             # Consider exiting if inclusion mode is active but no valid rules exist
             # return

    exclude_patterns_from_file = []
    if args.exclude_from:
        exclude_patterns_from_file = parse_pattern_file(args.exclude_from)

    # Normalize direct paths for efficient lookup and consistent matching
    # Use sets for direct include/exclude for faster lookups
    norm_include_dirs = {normalize_path(os.path.normpath(d)) for d in args.include_dirs}
    norm_include_files = {normalize_path(os.path.normpath(f)) for f in args.include_files}
    norm_exclude_dirs = {normalize_path(os.path.normpath(d)) for d in args.exclude_dirs}
    norm_exclude_files = {normalize_path(os.path.normpath(f)) for f in args.exclude_files}


    # Determine output filename
    current_dir_name = os.path.basename(os.getcwd())
    # Ensure filename is filesystem-friendly (replace invalid chars if dir name has them)
    safe_dir_name = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in current_dir_name).strip()
    output_file = f"__SUMMARY__{safe_dir_name}.txt"

    # Call the main function
    create_summary(
        output_filename=output_file,
        start_dir='.', # Run from current directory
        include_dirs=norm_include_dirs,
        include_files=norm_include_files,
        include_patterns=include_patterns_from_file,
        exclude_dirs=norm_exclude_dirs,
        exclude_files=norm_exclude_files,
        exclude_patterns=exclude_patterns_from_file, # Pass only patterns from file here
        inclusion_mode=inclusion_mode_active
    )

# Make sure this is the entry point if the script is run directly
if __name__ == "__main__":
    cli_entry_point()