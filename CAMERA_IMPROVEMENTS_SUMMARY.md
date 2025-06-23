# Camera Improvements Summary

## Overview

This document summarizes the comprehensive improvements made to the AI-Scale Data Collector to fix the persistent blue tint issue and enhance camera functionality.

## Key Changes Implemented

### 1. CameraThread Class Enhancements

#### **Default Settings Changed**

- **Auto White Balance**: Now ALWAYS enabled by default (`self.auto_wb = True`)
- **Native Mode**: Changed from `True` to `False` - now starts in custom mode
- **Default WB Gains**: Set to `[0.85, 1.0, 1.15]` (BGR) - aggressive blue reduction for IMX219

#### **Enhanced White Balance Algorithm**

- **Improved backlighting handling**: More conservative pixel selection to avoid overexposed areas
- **Center crop fallback**: Uses center region when backlighting is too extreme
- **IMX219-specific correction**: Applied sensor-specific correction factors
- **Temporal smoothing**: Uses median filtering for stability against outliers

#### **Always Process Frames**

- **Removed conditional processing**: Every frame is now processed regardless of control settings
- **Consistent color correction**: Blue tint correction applied to every frame
- **Enhanced processing pipeline**: White balance → Brightness/Contrast → Saturation → Dehaze

#### **Diagnostic Overlay System**

- **Visual debug mode**: Press Cmd+D to toggle diagnostic overlay
- **Real-time WB gains display**: Shows current BGR gains
- **Color balance bars**: Visual representation of RGB channel means
- **Sample region indicator**: Yellow box showing analyzed area

### 2. Main Application Updates

#### **Initialization Changes**

- **Forced custom mode**: Application starts in custom mode by default
- **Auto WB enabled**: White balance correction active from startup
- **UI state synchronization**: Native mode checkbox starts unchecked

#### **Setup Camera Method**

- **Custom mode initialization**: `native_mode=False` by default
- **UI feedback**: Updates native mode checkbox to reflect actual state
- **Error handling**: Better error messages for camera initialization

### 3. Camera Controls Widget Updates

#### **Default State Changes**

- **Native mode checkbox**: Starts unchecked (custom mode)
- **Reset function**: Resets to custom mode, not native mode
- **Warning dialog**: Added when switching to native mode

#### **Native Mode Warning**

- **User confirmation**: Warns that native mode disables color correction
- **Blue tint warning**: Specifically mentions potential blue tint issues
- **Default to No**: Dialog defaults to "No" to prevent accidental switching

### 4. Debug and Diagnostic Features

#### **Enhanced Debug Mode**

- **Cmd+D shortcut**: Toggle white balance debug overlay
- **Real-time information**: Shows mode, WB status, gains, temperature, tint, FPS
- **Color analysis**: Live RGB channel means with visual bars
- **Sample region**: Yellow box showing center analysis area

#### **Improved Logging**

- **WB warmup logging**: Shows gains during initial stabilization
- **Debug information**: Detailed logging when debug mode is active
- **Error handling**: Better error messages for processing failures

## Technical Implementation Details

### White Balance Algorithm Improvements

```python
# Enhanced pixel selection for backlighting
mask = (gray > 50) & (gray < 200)  # More conservative range
color_mask = (b_channel < 240) & (g_channel < 240) & (r_channel < 240)
mask = mask & color_mask

# IMX219-specific correction
imx219_correction = np.array([0.85, 1.0, 1.10])  # Reduce blue, boost red
gains = gains * imx219_correction

# Temporal smoothing with median
smoothed_gains = np.median(all_gains, axis=0)
```

### Frame Processing Pipeline

```python
# ALWAYS process every frame
if self.auto_wb:
    self.wb_gains = self._estimate_white_balance(processed_frame)
else:
    # Apply IMX219 correction even without specific WB settings
    self.wb_gains = np.array([0.85, 1.0, 1.15])

# Apply gains with proper clipping
for i in range(3):
    channel = processed_frame[:, :, i].astype(np.float32)
    channel *= self.wb_gains[i]
    processed_frame[:, :, i] = np.clip(channel, 0, 255).astype(np.uint8)
```

### Diagnostic Overlay System

```python
# Real-time information display
texts = [
    f"Mode: {'Native' if self.native_mode else 'Custom'}",
    f"Auto WB: {'ON' if self.auto_wb else 'OFF'}",
    f"WB Gains: B={self.wb_gains[0]:.2f} G={self.wb_gains[1]:.2f} R={self.wb_gains[2]:.2f}",
    f"Temperature: {self.manual_wb_temp}K",
    f"Tint: {self.wb_tint}",
    f"FPS: {self.fps:.1f}"
]
```

## User Experience Improvements

### **Immediate Benefits**

1. **No more blue tint**: Automatic correction from startup
2. **Better backlighting handling**: Improved performance in challenging lighting
3. **Visual feedback**: Debug overlay shows what's happening
4. **Warning system**: Prevents accidental disabling of color correction

### **Debug Features**

1. **Cmd+D**: Toggle diagnostic overlay
2. **Real-time monitoring**: See WB gains and color balance
3. **Visual indicators**: Color bars and sample regions
4. **Comprehensive logging**: Detailed information in console

### **Safety Features**

1. **Native mode warning**: Confirms before disabling color correction
2. **Default to custom mode**: Ensures color correction is always active
3. **Graceful fallbacks**: Handles extreme lighting conditions
4. **Error recovery**: Continues operation even if processing fails

## Testing Recommendations

### **Basic Functionality**

1. **Startup**: Verify camera starts with correct colors (no blue tint)
2. **Debug mode**: Press Cmd+D to see diagnostic overlay
3. **Native mode**: Try switching to native mode (should show warning)
4. **Reset**: Use reset button to return to defaults

### **Lighting Conditions**

1. **Indoor lighting**: Test under various indoor light sources
2. **Backlighting**: Test with bright windows or lights behind subject
3. **Mixed lighting**: Test with multiple light sources
4. **Low light**: Test in dimly lit conditions

### **Performance**

1. **Frame rate**: Monitor FPS during operation
2. **Memory usage**: Check for memory leaks during extended use
3. **CPU usage**: Monitor processing overhead
4. **Stability**: Test for crashes or freezes

## Troubleshooting

### **If Blue Tint Persists**

1. **Check debug mode**: Press Cmd+D to see current WB gains
2. **Verify custom mode**: Ensure native mode checkbox is unchecked
3. **Check lighting**: Ensure adequate lighting for WB estimation
4. **Restart application**: Sometimes needed after camera changes

### **If Debug Overlay Doesn't Work**

1. **Check shortcut**: Ensure Cmd+D is pressed (not Ctrl+D)
2. **Check console**: Look for debug mode toggle messages
3. **Restart camera**: Try switching cameras or restarting app

### **If Camera Doesn't Start**

1. **Check permissions**: Ensure camera access is granted
2. **Check connections**: Verify camera is properly connected
3. **Check other apps**: Ensure no other app is using the camera
4. **Check drivers**: Verify camera drivers are up to date

## Future Enhancements

### **Potential Improvements**

1. **Machine learning WB**: Train model on produce-specific lighting
2. **Advanced backlighting**: More sophisticated backlighting detection
3. **Color calibration**: User-specific color calibration tools
4. **Preset system**: Save and load custom WB settings

### **Performance Optimizations**

1. **GPU acceleration**: Use GPU for image processing
2. **Multi-threading**: Parallel processing for multiple operations
3. **Memory optimization**: Reduce memory footprint
4. **Caching**: Cache processed frames for better performance

## Conclusion

These improvements provide a comprehensive solution to the blue tint issue while adding valuable diagnostic and debugging capabilities. The camera now:

- **Always applies color correction** from startup
- **Handles challenging lighting** better than before
- **Provides visual feedback** for troubleshooting
- **Prevents accidental disabling** of color correction
- **Maintains performance** while adding features

The implementation is robust, user-friendly, and provides the foundation for future enhancements.
