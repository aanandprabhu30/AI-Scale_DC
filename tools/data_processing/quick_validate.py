#!/usr/bin/env python3
"""
Quick Dataset Validation for AI-Scale v2.2.0
Lightweight validation for integration with main application.
Now uses a central SQLite database for metadata.

Status: Camera improvements implemented, blue tint issue pending resolution
"""

import cv2
from pathlib import Path
from typing import Dict, List, Tuple
import sqlite3

def quick_validate_dataset(dataset_path: Path, db_path: Path) -> Dict:
    """
    Quick validation using the central database and filesystem checks.
    
    Args:
        dataset_path: The root path of the raw image data (e.g., 'data/raw').
        db_path: The path to the SQLite database file.
    """
    
    result = {
        "valid": True,
        "total_classes": 0,
        "total_images": 0,
        "total_size_mb": 0,
        "issues": [],
        "class_summary": {}
    }
    
    if not db_path.exists():
        result["valid"] = False
        result["issues"].append(f"Database not found at '{db_path}'")
        return result

    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()

        # --- Database-driven Validation ---
        # Get total images
        cur.execute("SELECT COUNT(id) FROM captures")
        result["total_images"] = cur.fetchone()[0]

        # Get total size
        cur.execute("SELECT SUM(file_size) FROM captures")
        total_size_bytes = cur.fetchone()[0]
        result["total_size_mb"] = (total_size_bytes / (1024 * 1024)) if total_size_bytes else 0

        # Get class summaries
        cur.execute("""
            SELECT class_name, COUNT(id), SUM(file_size)
            FROM captures
            GROUP BY class_name
        """)
        db_class_summary = cur.fetchall()
        result["total_classes"] = len(db_class_summary)

        for class_name, count, size_bytes in db_class_summary:
            class_info = {
                "count": count,
                "size_mb": (size_bytes / (1024 * 1024)) if size_bytes else 0,
                "issues": []
            }
            if count < 10:
                class_info["issues"].append(f"Low image count: {count}")
            
            result["class_summary"][class_name] = class_info

        # --- Filesystem-based Sanity Checks ---
        # Check for a few images to ensure they exist and are readable
        cur.execute("SELECT filename, class_name FROM captures ORDER BY RANDOM() LIMIT 20")
        sample_images = cur.fetchall()
        
        missing_files = []
        for filename, class_name in sample_images:
            img_path = dataset_path / class_name / filename
            if not img_path.exists():
                missing_files.append(f"{class_name}/{filename}")
            else:
                # Optional: check if image is loadable (can be slow)
                # try:
                #     img = cv2.imread(str(img_path))
                #     if img is None:
                #         result["class_summary"][class_name]["issues"].append(f"Cannot load: {filename}")
                # except Exception:
                #      result["class_summary"][class_name]["issues"].append(f"Read error: {filename}")
                pass
        
        if missing_files:
            issue_str = f"Found {len(missing_files)} missing image files (e.g., {missing_files[0]})"
            result["issues"].append(issue_str)
            result["valid"] = False

        con.close()

    except sqlite3.Error as e:
        result["valid"] = False
        result["issues"].append(f"Database error: {e}")
        return result

    # --- Overall Validation Rules ---
    if result["total_images"] < 100:
        result["issues"].append("Total images may be too low for training")
    
    if result["total_classes"] < 3:
        result["issues"].append("Too few classes for meaningful training")
    
    if result["issues"]:
        result["valid"] = False
    
    return result

def print_quick_report(report: Dict):
    """Prints a user-friendly report from the validation results."""
    print("--- Quick Dataset Validation Report ---")
    if report["valid"]:
        print("✅ Status: Looks Good!")
    else:
        print("❌ Status: Issues Found!")

    print(f"\nSummary:")
    print(f"  - Total Classes: {report['total_classes']}")
    print(f"  - Total Images: {report['total_images']}")
    print(f"  - Total Size: {report['total_size_mb']:.2f} MB")

    if report["issues"]:
        print("\nIssues:")
        # Print only unique, top-level issues
        for issue in sorted(list(set(report["issues"]))):
             # Don't print class-specific issues here, they are shown below
            if ":" not in issue:
                print(f"  - {issue}")


    print("\nClass Details:")
    if not report["class_summary"]:
        print("  - No classes found to detail.")
    else:
        for class_name, summary in sorted(report["class_summary"].items()):
            print(f"  - {class_name}: {summary['count']} images ({summary['size_mb']:.2f} MB)")
            if summary['issues']:
                for issue in summary['issues']:
                    print(f"    - ⚠️ {issue}")
    print("\n---------------------------------------")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Quickly validate an AI-Scale dataset using its database.")
    parser.add_argument("dataset_path", type=Path, help="Path to the root of the dataset (e.g., data/raw).")
    parser.add_argument("--db-path", type=Path, default="data/metadata.db", help="Path to the metadata SQLite database.")
    args = parser.parse_args()

    if not args.db_path.exists():
        print(f"Error: Database file not found at '{args.db_path}'")
        exit(1)

    validation_result = quick_validate_dataset(args.dataset_path, args.db_path)
    print_quick_report(validation_result) 