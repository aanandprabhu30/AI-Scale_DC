#!/usr/bin/env python3
"""
AI-Scale Dataset Validator v2.2.0
Validates collected dataset for training readiness by querying the central database.

Status: Camera improvements implemented, blue tint issue pending resolution
"""

import os
import json
import cv2
import numpy as np
from pathlib import Path
from collections import defaultdict
import argparse
import sqlite3
from datetime import datetime

def validate_dataset(dataset_path: Path, db_path: Path, output_report: Path = None):
    """Validate dataset structure and image quality using the database."""
    
    report = {
        "dataset_path": str(dataset_path),
        "database_path": str(db_path),
        "validation_time": datetime.now().isoformat(),
        "classes": {},
        "issues": [],
        "recommendations": []
    }
    
    if not db_path.exists():
        report["issues"].append(f"Database file does not exist at '{db_path}'")
        return report
        
    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()

        # Get all captures from the database
        cur.execute("SELECT class_name, filename, width, height, camera_settings FROM captures")
        all_captures = cur.fetchall()

        if not all_captures:
            report["issues"].append("No captures found in the database.")
            return report

        # Group captures by class
        class_data = defaultdict(list)
        for class_name, filename, width, height, camera_settings_json in all_captures:
            class_data[class_name].append({
                "filename": filename,
                "resolution": (width, height),
                "camera_settings": json.loads(camera_settings_json or '{}')
            })

    except (sqlite3.Error, json.JSONDecodeError) as e:
        report["issues"].append(f"Failed to query or parse database: {e}")
        return report
    finally:
        if 'con' in locals() and con:
            con.close()

    total_images = len(all_captures)
    
    for class_name, captures in class_data.items():
        class_info = {
            "image_count": len(captures),
            "resolutions": defaultdict(int),
            "brightness_values": [],
            "contrast_values": [],
            "saturation_values": [],
            "exposure_comp_values": [],
            "issues": []
        }
        
        # Validate each image record
        for capture in captures:
            # --- Filesystem Check ---
            img_path = dataset_path / class_name / capture["filename"]
            if not img_path.exists():
                class_info["issues"].append(f"Missing file on disk: {capture['filename']}")
                continue

            # --- Metadata Analysis ---
            res_str = f"{capture['resolution'][0]}x{capture['resolution'][1]}"
            class_info["resolutions"][res_str] += 1
            
            # Camera settings from software controls
            cam_settings = capture.get("camera_settings", {})
            class_info["brightness_values"].append(cam_settings.get("brightness", 0))
            class_info["contrast_values"].append(cam_settings.get("contrast", 0))
            class_info["saturation_values"].append(cam_settings.get("saturation", 0))
            class_info["exposure_comp_values"].append(cam_settings.get("exposure_comp", 0))

        # --- Class-level Analysis ---
        if class_info["image_count"] < 50:
            report["recommendations"].append(f"Class '{class_name}' has low image count: {class_info['image_count']} (recommend 50+)")
        
        if len(class_info["resolutions"]) > 1:
            class_info["issues"].append(f"Inconsistent resolutions found in '{class_name}': {list(class_info['resolutions'].keys())}")
            
        report["classes"][class_name] = class_info
    
    # --- Overall Recommendations ---
    if total_images < 500:
        report["recommendations"].append(f"Total images ({total_images}) is low for training. Aim for 1000+ images.")
    
    if len(class_data) < 5:
        report["recommendations"].append(f"Few classes ({len(class_data)}). Consider adding more variety.")
    
    # Check for class imbalance
    class_counts = [info["image_count"] for info in report["classes"].values()]
    if class_counts:
        max_count = max(class_counts)
        min_count = min(class_counts)
        if max_count > min_count * 3:
            report["recommendations"].append("Significant class imbalance detected. Consider augmenting smaller classes or collecting more data.")
    
    # Save report
    if output_report:
        output_report.parent.mkdir(parents=True, exist_ok=True)
        with open(output_report, 'w') as f:
            json.dump(report, f, indent=4)
    
    return report

def print_report(report):
    """Print validation report in readable format"""
    print("=" * 60)
    print("AI-SCALE DATASET VALIDATION REPORT")
    print("=" * 60)
    print(f"Dataset Path: {report.get('dataset_path')}")
    print(f"Database Path: {report.get('database_path')}")
    print(f"Validation Time: {report.get('validation_time')}")
    print()
    
    # Summary
    total_classes = len(report["classes"])
    total_images = sum(info["image_count"] for info in report["classes"].values())
    total_issues = sum(len(info["issues"]) for info in report["classes"].values())
    
    print(f"📊 SUMMARY:")
    print(f"   Classes: {total_classes}")
    print(f"   Total Images: {total_images}")
    print(f"   Issues Found: {total_issues}")
    print()
    
    # Class details
    print("📁 CLASS DETAILS:")
    for class_name, info in report["classes"].items():
        print(f"   {class_name.upper()}:")
        print(f"     - Images: {info['image_count']}")
        
        if info["resolutions"]:
            res_str = ", ".join([f"{res} ({count})" for res, count in info["resolutions"].items()])
            print(f"     - Resolutions: {res_str}")

        if info["brightness_values"]:
            avg_b = np.mean(info['brightness_values'])
            std_b = np.std(info['brightness_values'])
            print(f"     - Brightness:  Avg={avg_b:.1f}, StdDev={std_b:.1f}")

        if info["contrast_values"]:
            avg_c = np.mean(info['contrast_values'])
            std_c = np.std(info['contrast_values'])
            print(f"     - Contrast:    Avg={avg_c:.1f}, StdDev={std_c:.1f}")
            
        if info["saturation_values"]:
            avg_s = np.mean(info['saturation_values'])
            std_s = np.std(info['saturation_values'])
            print(f"     - Saturation:  Avg={avg_s:.1f}, StdDev={std_s:.1f}")

        if info["issues"]:
            print(f"     - Issues Found: {len(info['issues'])}")
            for issue in info["issues"][:3]:  # Show first 3 issues
                print(f"       - {issue}")
            if len(info["issues"]) > 3:
                print(f"       ... and {len(info['issues']) - 3} more")
        print()
    
    # Recommendations
    if report["recommendations"]:
        print("💡 RECOMMENDATIONS:")
        for rec in report["recommendations"]:
            print(f"   - {rec}")
        print()
    
    # Overall status
    if total_issues == 0 and total_images > 0:
        print("✅ Dataset validation passed!")
    else:
        print(f"⚠️  Dataset has {total_issues} issues and/or recommendations to address.")

def main():
    parser = argparse.ArgumentParser(
        description="Validate an AI-Scale dataset by querying its database.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("dataset_path", type=Path, help="Path to the root dataset directory (e.g., 'data/raw').")
    parser.add_argument("--db-path", type=Path, default="data/metadata.db", help="Path to the metadata SQLite database.")
    parser.add_argument("--output", "-o", type=Path, help="Path to save the JSON output report file.")
    
    args = parser.parse_args()
    
    report = validate_dataset(args.dataset_path, args.db_path, args.output)
    print_report(report)

if __name__ == "__main__":
    main() 