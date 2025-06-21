import cv2
import time

def test_camera(index: int):
    """Tests a single camera index and displays its feed."""
    print(f"--- Testing Camera Index: {index} ---")
    
    # Use the AVFoundation backend, best for macOS
    cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)

    if not cap.isOpened():
        print(f"❌ Error: Could not open camera at index {index}")
        return

    # Get camera properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"✅ Camera opened successfully!")
    print(f"   Default Resolution: {width}x{height}")
    print(f"   Default FPS: {fps}")
    print("   Displaying feed... Press 'q' in the window to quit.")
    
    window_name = f'Camera Test (Index {index}) - Press Q to Quit'

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            print("\n❌ Error: Can't receive frame. Stream might have ended.")
            break

        cv2.imshow(window_name, frame)

        # Check for 'q' key press to exit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    print("--- Test Finished ---")
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    # We will test camera index 0, as that's what the app is trying to use.
    test_camera(0) 