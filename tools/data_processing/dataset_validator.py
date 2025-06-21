#!/usr/bin/env python3
"""
AI-Scale Dataset Validator
Validates collected dataset for training readiness
"""

import os
import json
import cv2
import numpy as np
from pathlib import Path
from collections import defaultdict
import argparse

def validate_dataset(dataset_path: Path, output_report: Path = None):
    """Validate dataset structure and image quality"""
    
    report = {
        "dataset_path": str(dataset_path),
        "validation_time": "",
        "classes": {},
        "issues": [],
        "recommendations": []
    }
    
    if not dataset_path.exists():
        report["issues"].append("Dataset path does not exist")
        return report
    
    # Check class directories
    class_dirs = [d for d in dataset_path.iterdir() if d.is_dir() and not d.name.startswith('.')]
    
    if not class_dirs:
        report["issues"].append("No class directories found")
        return report
    
    total_images = 0
    total_size = 0
    
    for class_dir in class_dirs:
        class_name = class_dir.name
        class_info = {
            "image_count": 0,
            "total_size_mb": 0,
            "resolutions": defaultdict(int),
            "framerates": defaultdict(int),
            "brightness_values": [],
            "contrast_values": [],
            "issues": []
        }
        
        # Check images in class
        image_files = sorted(list(class_dir.glob("*.jpg")) + list(class_dir.glob("*.jpeg")))
        
        if not image_files:
            class_info["issues"].append("No images found")
            report["classes"][class_name] = class_info
            continue
        
        class_info["image_count"] = len(image_files)
        total_images += len(image_files)
        
        # Validate each image
        for img_path in image_files:
            try:
                # --- Basic File Check ---
                file_size = img_path.stat().st_size
                class_info["total_size_mb"] += file_size / (1024 * 1024)
                total_size += file_size
                
                # --- Image Loading Check ---
                img = cv2.imread(str(img_path))
                if img is None:
                    class_info["issues"].append(f"Cannot load image: {img_path.name}")
                    continue
                
                # --- Metadata Check ---
                meta_path = img_path.with_suffix('.json')
                if meta_path.exists():
                    with open(meta_path, 'r') as f:
                        metadata = json.load(f)
                    
                    # Resolution
                    res = tuple(metadata.get("resolution", (0,0)))
                    class_info["resolutions"][f"{res[0]}x{res[1]}"] += 1
                    
                    # Camera settings
                    cam_settings = metadata.get("camera_settings", {})
                    fps = cam_settings.get("fps", 0)
                    if fps > 0:
                        class_info["framerates"][str(fps)] += 1
                    
                    brightness = cam_settings.get("brightness")
                    if brightness is not None:
                        class_info["brightness_values"].append(brightness)
                        
                    contrast = cam_settings.get("contrast")
                    if contrast is not None:
                        class_info["contrast_values"].append(contrast)

                else:
                    # Fallback if no metadata exists
                    height, width = img.shape[:2]
                    class_info["resolutions"][f"{width}x{height}"] += 1
                    class_info["issues"].append(f"No metadata file for: {img_path.name}")
                    
            except Exception as e:
                class_info["issues"].append(f"Error processing {img_path.name}: {str(e)}")
        
        # --- Class-level Analysis ---
        if class_info["image_count"] < 50:
            class_info["issues"].append(f"Low image count: {class_info['image_count']} (recommend 50+)")
        
        if len(class_info["resolutions"]) > 1:
            class_info["issues"].append(f"Inconsistent resolutions found: {list(class_info['resolutions'].keys())}")
        
        if len(class_info["framerates"]) > 1:
            class_info["issues"].append(f"Inconsistent framerates found: {list(class_info['framerates'].keys())}")
            
        report["classes"][class_name] = class_info
    
    # --- Overall Recommendations ---
    if total_images < 500:
        report["recommendations"].append(f"Total images ({total_images}) is low for training. Aim for 1000+ images.")
    
    if len(class_dirs) < 5:
        report["recommendations"].append(f"Few classes ({len(class_dirs)}). Consider adding more variety.")
    
    # Check for class imbalance
    class_counts = [info["image_count"] for info in report["classes"].values()]
    if class_counts:
        max_count = max(class_counts)
        min_count = min(class_counts)
        if max_count > min_count * 3:
            report["recommendations"].append("Class imbalance detected. Consider balancing dataset.")
    
    # Save report
    if output_report:
        with open(output_report, 'w') as f:
            json.dump(report, f, indent=2)
    
    return report

def print_report(report):
    """Print validation report in readable format"""
    print("=" * 60)
    print("AI-SCALE DATASET VALIDATION REPORT")
    print("=" * 60)
    print(f"Dataset: {report['dataset_path']}")
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
        print(f"   {class_name}:")
        print(f"     - Images: {info['image_count']}")
        print(f"     - Size: {info['total_size_mb']:.1f} MB")
        
        if info["resolutions"]:
            res_str = ", ".join([f"{res} ({count})" for res, count in info["resolutions"].items()])
            print(f"     - Resolutions: {res_str}")
        
        if info["framerates"]:
            fps_str = ", ".join([f"{fps}fps ({count})" for fps, count in info["framerates"].items()])
            print(f"     - Framerates: {fps_str}")
            
        if info["brightness_values"]:
            avg_b = np.mean(info['brightness_values'])
            std_b = np.std(info['brightness_values'])
            print(f"     - Brightness: Avg={avg_b:.2f}, StdDev={std_b:.2f}")

        if info["contrast_values"]:
            avg_c = np.mean(info['contrast_values'])
            std_c = np.std(info['contrast_values'])
            print(f"     - Contrast:   Avg={avg_c:.2f}, StdDev={std_c:.2f}")

        if info["issues"]:
            print(f"     - Issues: {len(info['issues'])}")
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
    if total_issues == 0:
        print("✅ Dataset validation passed!")
    else:
        print(f"⚠️  Dataset has {total_issues} issues to address")

def main():
    parser = argparse.ArgumentParser(description="Validate AI-Scale dataset")
    parser.add_argument("dataset_path", type=Path, help="Path to dataset directory")
    parser.add_argument("--output", "-o", type=Path, help="Output report file")
    
    args = parser.parse_args()
    
    report = validate_dataset(args.dataset_path, args.output)
    print_report(report)

if __name__ == "__main__":
    main() 