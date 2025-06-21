#!/usr/bin/env python3
"""
Quick Dataset Validation for AI-Scale
Lightweight validation for integration with main application
"""

import cv2
from pathlib import Path
from typing import Dict, List, Tuple

def quick_validate_dataset(dataset_path: Path) -> Dict:
    """Quick validation of dataset structure and basic quality"""
    
    result = {
        "valid": True,
        "total_classes": 0,
        "total_images": 0,
        "total_size_mb": 0,
        "issues": [],
        "class_summary": {}
    }
    
    if not dataset_path.exists():
        result["valid"] = False
        result["issues"].append("Dataset path does not exist")
        return result
    
    # Check class directories
    class_dirs = [d for d in dataset_path.iterdir() 
                  if d.is_dir() and not d.name.startswith('.')]
    
    result["total_classes"] = len(class_dirs)
    
    if not class_dirs:
        result["valid"] = False
        result["issues"].append("No class directories found")
        return result
    
    for class_dir in class_dirs:
        class_name = class_dir.name
        image_files = list(class_dir.glob("*.jpg")) + list(class_dir.glob("*.jpeg"))
        
        class_info = {
            "count": len(image_files),
            "size_mb": 0,
            "issues": []
        }
        
        if len(image_files) < 10:
            class_info["issues"].append(f"Low image count: {len(image_files)}")
        
        for img_path in image_files:
            try:
                file_size = img_path.stat().st_size
                class_info["size_mb"] += file_size / (1024 * 1024)
                result["total_size_mb"] += file_size / (1024 * 1024)
                
                # Quick image validation
                img = cv2.imread(str(img_path))
                if img is None:
                    class_info["issues"].append(f"Cannot load: {img_path.name}")
                elif img.shape[0] < 50 or img.shape[1] < 50:
                    class_info["issues"].append(f"Too small: {img_path.name}")
                    
            except Exception as e:
                class_info["issues"].append(f"Error: {img_path.name}")
        
        result["total_images"] += class_info["count"]
        result["class_summary"][class_name] = class_info
        
        if class_info["issues"]:
            result["issues"].extend([f"{class_name}: {issue}" for issue in class_info["issues"]])
    
    # Overall validation
    if result["total_images"] < 100:
        result["issues"].append("Total images too low for training")
    
    if result["total_classes"] < 3:
        result["issues"].append("Too few classes for meaningful training")
    
    if result["issues"]:
        result["valid"] = False
    
    return result

def get_dataset_stats(dataset_path: Path) -> Dict:
    """Get basic dataset statistics"""
    
    stats = {
        "classes": {},
        "total_images": 0,
        "total_size_mb": 0,
        "avg_images_per_class": 0
    }
    
    if not dataset_path.exists():
        return stats
    
    class_dirs = [d for d in dataset_path.iterdir() 
                  if d.is_dir() and not d.name.startswith('.')]
    
    for class_dir in class_dirs:
        image_files = list(class_dir.glob("*.jpg")) + list(class_dir.glob("*.jpeg"))
        class_size = sum(f.stat().st_size for f in image_files) / (1024 * 1024)
        
        stats["classes"][class_dir.name] = {
            "count": len(image_files),
            "size_mb": class_size
        }
        
        stats["total_images"] += len(image_files)
        stats["total_size_mb"] += class_size
    
    if stats["classes"]:
        stats["avg_images_per_class"] = stats["total_images"] / len(stats["classes"])
    
    return stats 