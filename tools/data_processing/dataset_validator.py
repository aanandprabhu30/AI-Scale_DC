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
            "resolutions": [],
            "file_sizes": [],
            "issues": []
        }
        
        # Check images in class
        image_files = list(class_dir.glob("*.jpg")) + list(class_dir.glob("*.jpeg")) + list(class_dir.glob("*.png"))
        
        if not image_files:
            class_info["issues"].append("No images found")
            report["classes"][class_name] = class_info
            continue
        
        class_info["image_count"] = len(image_files)
        total_images += len(image_files)
        
        # Validate each image
        for img_path in image_files:
            try:
                # Check file size
                file_size = img_path.stat().st_size
                class_info["total_size_mb"] += file_size / (1024 * 1024)
                total_size += file_size
                class_info["file_sizes"].append(file_size)
                
                # Check image can be loaded
                img = cv2.imread(str(img_path))
                if img is None:
                    class_info["issues"].append(f"Cannot load image: {img_path.name}")
                    continue
                
                # Check resolution
                height, width = img.shape[:2]
                class_info["resolutions"].append((width, height))
                
                # Check for very small images
                if width < 100 or height < 100:
                    class_info["issues"].append(f"Very small image: {img_path.name} ({width}x{height})")
                
                # Check for very large images
                if width > 5000 or height > 5000:
                    class_info["issues"].append(f"Very large image: {img_path.name} ({width}x{height})")
                    
            except Exception as e:
                class_info["issues"].append(f"Error processing {img_path.name}: {str(e)}")
        
        # Class-specific recommendations
        if class_info["image_count"] < 50:
            class_info["issues"].append(f"Low image count: {class_info['image_count']} (recommend 50+)")
        
        if class_info["image_count"] > 0:
            avg_size = class_info["total_size_mb"] / class_info["image_count"]
            if avg_size > 5:  # 5MB per image
                class_info["issues"].append(f"Large average file size: {avg_size:.1f}MB per image")
        
        report["classes"][class_name] = class_info
    
    # Overall recommendations
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
        print(f"     Images: {info['image_count']}")
        print(f"     Size: {info['total_size_mb']:.1f} MB")
        
        if info["resolutions"]:
            unique_res = set(info["resolutions"])
            print(f"     Resolutions: {len(unique_res)} unique")
        
        if info["issues"]:
            print(f"     Issues: {len(info['issues'])}")
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