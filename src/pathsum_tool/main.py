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
        with open(file_path, 'r', encoding='utf-8', errors='strict') as f:
            f.read(1024) # Try reading a small chunk
        return True
    except UnicodeDecodeError:
        # print(f"Skipping binary file (UnicodeDecodeError): {file_path}")
        return False
    except OSError: # Handle cases like permission errors or special files
        # print(f"Skipping non-regular or inaccessible file: {file_path}")
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
                   exclude_dirs=None, exclude_files=None,
                   include_patterns=None, exclude_patterns=None):
    """
    Walks the directory tree, reads text files based on include/exclude rules,
    and writes their content to the output file, separated by headers.

    Args:
        output_filename (str): The name of the summary file to create.
        start_dir (str): The root directory to start scanning.
        exclude_dirs (list): List of directory paths (relative) to exclude directly.
        exclude_files (list): List of file paths/names (relative) to exclude directly.
        include_patterns (list): List of fnmatch patterns. If provided, ONLY paths
                                 matching these patterns are considered.
        exclude_patterns (list): List of fnmatch patterns (from file + CLI) to exclude.
    """
    exclude_dirs = exclude_dirs or []
    exclude_files = exclude_files or []
    include_patterns = include_patterns or []
    exclude_patterns = exclude_patterns or [] # Combined CLI and file patterns

    # --- Prepare patterns and initial exclusions ---
    # Normalize direct exclusions for simple matching first
    # Use normpath for OS-specific normalization, then normalize_path for matching
    normalized_exclude_dirs = {normalize_path(os.path.normpath(d)) for d in exclude_dirs}
    normalized_exclude_files = {normalize_path(os.path.normpath(f)) for f in exclude_files}

    # Also add direct file exclusions to the pattern list for fnmatch consistency
    exclude_patterns.extend(normalized_exclude_files)
    # Add directory exclusions potentially as patterns too (e.g., ending with /)
    exclude_patterns.extend([d + '/' if not d.endswith('/') else d for d in normalized_exclude_dirs])


    # Always exclude the summary file itself
    summary_file_norm = normalize_path(os.path.normpath(output_filename))
    normalized_exclude_files.add(summary_file_norm)
    # Add summary file to patterns as well to be safe
    if summary_file_norm not in exclude_patterns:
         exclude_patterns.append(summary_file_norm)


    skipped_dirs_count = 0
    skipped_files_count = 0
    processed_files_count = 0
    explicitly_included_count = 0
    explicitly_excluded_count = 0

    print(f"Starting summary creation. Output file: {output_filename}")
    if include_patterns:
        print(f"Inclusion mode active. Only considering paths matching: {include_patterns}")
    print(f"Excluding directories directly matching: {normalized_exclude_dirs}")
    print(f"Excluding files directly matching: {normalized_exclude_files}")
    print(f"Excluding paths matching patterns: {exclude_patterns}")
    print("-" * 20)

    try:
        with open(output_filename, 'w', encoding='utf-8') as outfile:
            # os.walk iterates through directory tree top-down
            for dirpath, dirnames, filenames in os.walk(start_dir, topdown=True):

                # --- Directory Exclusion (applied before descending) ---
                dirs_to_remove = []
                original_dirnames = list(dirnames) # Copy for iteration while modifying

                for dirname in original_dirnames:
                    current_dir_abs = os.path.normpath(os.path.join(dirpath, dirname))
                    current_dir_rel = normalize_path(os.path.relpath(current_dir_abs, start_dir))
                    current_dir_rel_with_slash = current_dir_rel + '/'


                    # Check direct exclusion first
                    is_excluded = False
                    if current_dir_rel in normalized_exclude_dirs:
                        is_excluded = True
                    else:
                        # Check pattern exclusion (match against path with trailing slash)
                        for pattern in exclude_patterns:
                            # Match full relative path or just the directory name
                            if fnmatch.fnmatch(current_dir_rel_with_slash, pattern) or \
                               fnmatch.fnmatch(dirname, pattern.rstrip('/')): # Match dir name if pattern doesn't specify path
                                is_excluded = True
                                break

                    if is_excluded:
                        # print(f"Excluding directory tree: {current_dir_rel}")
                        dirs_to_remove.append(dirname)
                        skipped_dirs_count += 1 # Simplistic count

                # Remove the directories from the list os.walk will visit next
                for d in dirs_to_remove:
                     if d in dirnames: # Avoid error if already removed
                         dirnames.remove(d)

                # --- File Processing and Filtering ---
                for filename in filenames:
                    file_abs_path = os.path.normpath(os.path.join(dirpath, filename))
                    file_rel_path = normalize_path(os.path.relpath(file_abs_path, start_dir))

                    # --- Step 1: Inclusion Check (if include_patterns is active) ---
                    should_include = not include_patterns # Include if list is empty (default)
                    if include_patterns:
                        for pattern in include_patterns:
                            # Match against relative path or just filename
                            if fnmatch.fnmatch(file_rel_path, pattern) or fnmatch.fnmatch(filename, pattern):
                                should_include = True
                                break
                        if not should_include:
                            # If include patterns exist but this file doesn't match any, skip it.
                            # print(f"Skipping (doesn't match include patterns): {file_rel_path}")
                            skipped_files_count += 1
                            continue
                        else:
                            # Only count if include_patterns was active and we passed
                            explicitly_included_count +=1


                    # --- Step 2: Exclusion Check ---
                    is_excluded = False
                    # Check direct file exclusion first
                    if file_rel_path in normalized_exclude_files or filename in normalized_exclude_files:
                         is_excluded = True
                    else:
                        # Check pattern exclusion
                        for pattern in exclude_patterns:
                            # Match against relative path or just filename
                            if fnmatch.fnmatch(file_rel_path, pattern) or fnmatch.fnmatch(filename, pattern):
                                is_excluded = True
                                break

                    if is_excluded:
                        # print(f"Skipping (excluded): {file_rel_path}")
                        explicitly_excluded_count += 1
                        skipped_files_count += 1
                        continue

                    # --- Step 3: Text File Check and Content Addition ---
                    if is_likely_text_file(file_abs_path):
                        # print(f"Adding: {file_rel_path}")
                        try:
                            with open(file_abs_path, 'r', encoding='utf-8', errors='ignore') as infile: # Use ignore on final read just in case
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
    if include_patterns:
        print(f"Considered {explicitly_included_count} files based on include patterns.")
    print(f"Skipped {skipped_files_count} files (excluded, non-matching include, binary, or errors).")
    if explicitly_excluded_count > 0:
        print(f"({explicitly_excluded_count} files matched explicit exclude rules/patterns).")
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
        epilog="""Pattern files (for --include-from/--exclude-from) use .gitignore-like syntax:
  - Each line is a pattern.
  - Lines starting with # are comments.
  - Blank lines are ignored.
  - Patterns are matched against paths relative to the starting directory (using forward slashes '/').
  - Standard wildcards (*, ?, [seq]) can be used.
  - If a pattern ends with '/', it only matches directories.

Examples:
  # Basic usage
  pathsum

  # Exclude specific directories and files via CLI
  pathsum --exclude-dirs node_modules build dist .git venv --exclude-files secrets.yaml *.log

  # Exclude patterns from a file (e.g., .pathsumignore)
  pathsum --exclude-from .pathsumignore

  # ONLY include files/dirs matching patterns in a file (e.g., .pathsuminclude)
  pathsum --include-from .pathsuminclude

  # Combine include file and exclude file/flags
  pathsum --include-from .pathsuminclude --exclude-from .gitignore --exclude-files temp.txt
"""
    )

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
    parser.add_argument(
        "--include-from",
        metavar='FILE',
        help="Specify a file containing patterns. ONLY files/directories matching these patterns will be included."
    )

    args = parser.parse_args()

    # --- Process patterns from files ---
    include_patterns = []
    if args.include_from:
        include_patterns = parse_pattern_file(args.include_from)
        if not include_patterns:
             print(f"Warning: Include file '{args.include_from}' was empty or not found. No files will be included.")
             # Decide if you want to exit or proceed (currently proceeds, resulting in empty output)
             # return # Or exit

    exclude_patterns_from_file = []
    if args.exclude_from:
        exclude_patterns_from_file = parse_pattern_file(args.exclude_from)

    # Combine CLI excludes and file excludes into a single list for create_summary
    # Note: create_summary further processes these patterns
    all_exclude_patterns = exclude_patterns_from_file # Start with patterns from file

    # Determine output filename
    current_dir_name = os.path.basename(os.getcwd())
    output_file = f"__SUMMARY__{current_dir_name}.txt"

    # Call the main function
    create_summary(
        output_filename=output_file,
        exclude_dirs=args.exclude_dirs,
        exclude_files=args.exclude_files,
        include_patterns=include_patterns,
        exclude_patterns=all_exclude_patterns # Pass combined patterns here
    )

# Make sure this is the entry point if the script is run directly
# (though setup.py uses cli_entry_point directly)
if __name__ == "__main__":
    cli_entry_point()
