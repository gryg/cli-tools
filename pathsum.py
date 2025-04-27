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
        with open(file_path, 'r', encoding='utf-8') as f:
            f.read(1024) # Try reading a small chunk
        return True
    except UnicodeDecodeError:
        # print(f"Skipping binary file (UnicodeDecodeError): {file_path}")
        return False
    except Exception as e:
        # Handle other potential errors like permission issues
        print(f"Warning: Could not read file {file_path}. Error: {e}")
        return False

# --- Main Logic ---

def create_summary(output_filename, exclude_dirs=None, exclude_files=None):
    """
    Walks the current directory, reads text files, and writes their content
    to the output file, separated by headers.
    """
    start_dir = '.'
    exclude_dirs = exclude_dirs or []
    exclude_files = exclude_files or []

    # Normalize exclusion paths for comparison
    # Use os.path.normpath to handle './' and slashes consistently
    normalized_exclude_dirs = {os.path.normpath(d) for d in exclude_dirs}
    normalized_exclude_files = {os.path.normpath(f) for f in exclude_files}

    # Always exclude the summary file itself
    normalized_exclude_files.add(os.path.normpath(output_filename))

    skipped_dirs_count = 0
    skipped_files_count = 0
    processed_files_count = 0

    print(f"Starting summary creation. Output file: {output_filename}")
    print(f"Excluding directories matching: {normalized_exclude_dirs}")
    print(f"Excluding files matching: {normalized_exclude_files}")
    print("-" * 20)

    try:
        with open(output_filename, 'w', encoding='utf-8') as outfile:
            # os.walk iterates through directory tree top-down
            for dirpath, dirnames, filenames in os.walk(start_dir, topdown=True):
                # --- Directory Exclusion ---
                # Modify dirnames *in place* to prevent os.walk from descending
                # into excluded directories.
                dirs_to_remove = []
                for i, dirname in enumerate(dirnames):
                    current_check_dir = os.path.normpath(os.path.join(dirpath, dirname))
                    # Check if the current directory *or any of its parents* start with an excluded path
                    # Or use fnmatch for wildcard matching if desired:
                    # if any(fnmatch.fnmatch(current_check_dir, pattern) for pattern in normalized_exclude_dirs):
                    if any(current_check_dir == excluded_dir or current_check_dir.startswith(excluded_dir + os.sep)
                           for excluded_dir in normalized_exclude_dirs):
                         print(f"Excluding directory and its contents: {current_check_dir}")
                         dirs_to_remove.append(dirname)
                         skipped_dirs_count += 1 # Simplistic count, doesn't count subdirs skipped due to parent

                # Remove the directories from the list os.walk will visit next
                # Must iterate backwards or use a copy if removing while iterating index
                for d in dirs_to_remove:
                     dirnames.remove(d)


                # --- File Processing and Exclusion ---
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    normalized_file_path = os.path.normpath(file_path)

                    # Check file exclusion
                    # Use fnmatch for pattern matching (e.g., '*.log', 'temp_*'):
                    # if any(fnmatch.fnmatch(normalized_file_path, pattern) for pattern in normalized_exclude_files) or \
                    #    any(fnmatch.fnmatch(filename, pattern) for pattern in normalized_exclude_files):
                    if normalized_file_path in normalized_exclude_files or filename in normalized_exclude_files:
                        # print(f"Excluding file explicitly: {normalized_file_path}")
                        skipped_files_count += 1
                        continue

                    # Check if it's likely a text file
                    if is_likely_text_file(normalized_file_path):
                        print(f"Adding: {normalized_file_path}")
                        try:
                            with open(normalized_file_path, 'r', encoding='utf-8') as infile:
                                content = infile.read()

                            # Write header (using normalized path relative to start_dir)
                            relative_path = os.path.relpath(normalized_file_path, start_dir)
                            # Ensure consistent path separators (e.g., use forward slashes)
                            header_path = relative_path.replace(os.sep, '/')
                            outfile.write(f"# {header_path}\n")
                            outfile.write(content)
                            outfile.write("\n\n") # Add two newlines for separation
                            processed_files_count += 1
                        except Exception as e:
                            print(f"Error reading or writing file {normalized_file_path}: {e}")
                            skipped_files_count += 1
                    else:
                         # print(f"Skipping binary/unreadable file: {normalized_file_path}")
                         skipped_files_count += 1

    except IOError as e:
        print(f"Error opening or writing summary file {output_filename}: {e}")
        return # Exit if we can't write the main file

    print("-" * 20)
    print(f"Summary creation complete: {output_filename}")
    print(f"Processed {processed_files_count} text files.")
    print(f"Skipped {skipped_files_count} files (binary, explicitly excluded, or errors).")
    if skipped_dirs_count > 0:
      print(f"Skipped descending into {skipped_dirs_count} explicitly excluded directory trees.")


# --- Script Execution ---
def cli_entry_point():
    """
    This function is the entry point for the command-line tool.
    It parses arguments and calls the main logic.
    """
    parser = argparse.ArgumentParser(
        description="Summarize all text files in the current directory and subdirectories into a single file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  pathsum
  pathsum --exclude-dirs node_modules build dist .git venv
  pathsum --exclude-files secrets.txt config.yaml *.log
  pathsum --exclude-dirs ./build --exclude-files ./src/ignore_this.py
"""
    )
    parser.add_argument(
        "--exclude-dirs",
        nargs='+',
        metavar='DIR',
        help="Space-separated list of directory paths to exclude (e.g., node_modules .git build)."
    )
    parser.add_argument(
        "--exclude-files",
        nargs='+',
        metavar='FILE_OR_PATTERN',
        help="Space-separated list of file names or paths to exclude (e.g., secrets.txt *.log temp.data)."
    )
    args = parser.parse_args()

    current_dir_name = os.path.basename(os.getcwd())
    output_file = f"__SUMMARY__{current_dir_name}.txt"

    create_summary(output_file, args.exclude_dirs, args.exclude_files)


# The following block is no longer strictly needed when installed via pip,
# but can be useful for testing the script directly during development.
# if __name__ == "__main__":
#     cli_entry_point()