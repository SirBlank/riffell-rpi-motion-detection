import cv2
import EasyPySpin
import time
from time import sleep, perf_counter
import numpy as np
from datetime import datetime
from collections import deque

# OS Version: Ubuntu 22.04.4
# Python: 3.10.12
# spinnaker: 4.0.0.116
# spinnaker-python: 4.0.0.116
# EasyPySpin: 2.0.1
# opencv-python: 4.10.0.84
# numpy: 1.26.4

# Exposure Time: 4000 microseconds
# Gain: 1
# Turn off all auto configurations

serial_number_0 = "24122966"  # primary camera serial number
serial_number_1 = "24122965"  # secondary camera serial number
cap = EasyPySpin.SynchronizedVideoCapture(serial_number_0, serial_number_1)
cap.set(cv2.CAP_PROP_FPS, 200)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1440)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
cap.set(cv2.CAP_PROP_EXPOSURE, 4000)
cap.set(cv2.CAP_PROP_GAIN, 10)
fourcc = cv2.VideoWriter_fourcc(*'XVID')
out_0 = None
out_1 = None
buffer_size = 180
additional_frame_size = 1200
additional_frames_0 = deque(maxlen=additional_frame_size)
additional_frames_1 = deque(maxlen=additional_frame_size)
ring_buffer_0 = deque(maxlen=buffer_size)
ring_buffer_1 = deque(maxlen=buffer_size)
print(cap.get(cv2.CAP_PROP_EXPOSURE))

def detect_motion(frame, back_sub, kernel, min_contour_area, i):
    t1_start = perf_counter()
    fg_mask = back_sub.apply(frame)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
    fg_mask = cv2.medianBlur(fg_mask, 5)
    _, fg_mask = cv2.threshold(fg_mask, 127, 255, cv2.THRESH_BINARY)

    contours, _ = cv2.findContours(fg_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    areas = [cv2.contourArea(c) for c in contours]

    if len(areas) ==0:
        return None
    else:
        max_index = np.argmax(areas)
        if areas[max_index] > min_contour_area:
            t1_stop = perf_counter()
            print("t1:", t1_stop-t1_start)
            return contours[max_index]
    return None

def motion_detection():
    sleep(5)
    print("Starting motion detection. Press Ctrl+C to stop.")
    global out_0
    global out_1
    prev_x = None
    recording = False
    frame_counter = 0
    is_motion_detected_0 = False
    is_motion_detected_1 = False

    # INCREASE varThreshold = LESS SENSITIVE MOTION DETECTION
    back_sub = cv2.createBackgroundSubtractorMOG2(history=400, varThreshold=60, detectShadows=False)
    # INCREASE KERNEL SIZE FOR MORE AGGRESSIVE NOISE REDUCTION
    kernel = np.ones((30, 30), np.uint8)
    # DETERMINES THE CONTOUR SIZE TO BE CONSIDERED AS VALID MOTION
    # ONLY CONTOURS WITH AN AREA OF 1000 PIXELS OR MORE WILL BE CONSIDERED AS VALID MOTION.
    min_contour_area = 100

    while True:
        read_values = cap.read()
        for i, (ret, frame) in enumerate(read_values):
            t2_start = perf_counter()
            if not ret:
                print("Error: Failed to capture image")
                break

            if not recording:
                if i == 0:
                    ring_buffer_0.append(frame)
                elif i == 1:
                    ring_buffer_1.append(frame)
            t2_stop = perf_counter()
            # print("t2:", t2_stop-t2_start)

            frame_copy = np.copy(frame)
            if not recording:
                contour = detect_motion(frame_copy, back_sub, kernel, min_contour_area, i)

            if contour is not None:
                x, y, w, h = cv2.boundingRect(contour)
                x2 = x + int(w / 2)
                y2 = y + int(h / 2)

                if i == 0:
                    is_motion_detected_0 = True
                elif i == 1:
                    is_motion_detected_1 = True

                if is_motion_detected_0 and is_motion_detected_1 and prev_x is not None and x2 < prev_x and not recording:
                    print("Motion Detected!")
                    print("Start: ", datetime.now().strftime("%Y%-m-%d_%H:%M:%S.%f")[:-3])
                    start_time = time.time()
                    recording = True
                    frame_counter = 0
                    frame_height, frame_width = frame.shape[:2]
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_")
                    print(frame_width, frame_height)
                    out_0 = cv2.VideoWriter(f'motion_detection_{timestamp}_0.avi', fourcc, 140.0, (frame_width, frame_height), isColor=False)
                    out_1 = cv2.VideoWriter(f'motion_detection_{timestamp}_1.avi', fourcc, 140.0, (frame_width, frame_height), isColor=False)

                    is_motion_detected_0 = False
                    is_motion_detected_1 = False
                prev_x = x2
            else:
                if i == 0:
                    is_motion_detected_0 = False
                elif i == 1:
                    is_motion_detected_1 = False

            if recording:
                if i == 0:
                    additional_frames_0.append(frame)
                elif i == 1:
                    additional_frames_1.append(frame)
                frame_counter += .5 
                if frame_counter >= additional_frame_size:
                    recording = False
                    print("End: ", datetime.now().strftime("%Y%-m-%d_%H:%M:%S.%f")[:-3])
                    print("Finished recording. Retrieving buffer and saving video...")
                    print("Elapsed time:", time.time() - start_time)
                    for frame in ring_buffer_0:
                        out_0.write(frame)
                    for frame in additional_frames_0:
                        out_0.write(frame)
                    for frame in ring_buffer_1:
                        out_1.write(frame)
                    for frame in additional_frames_1:
                        out_1.write(frame)
                    out_0.release()
                    out_1.release()
                    print("Video Saved!")
                    additional_frames_0.clear()
                    additional_frames_1.clear()
                    ring_buffer_0.clear()
                    ring_buffer_1.clear()
                    back_sub = cv2.createBackgroundSubtractorMOG2(history=180, varThreshold=60, detectShadows=False)

if __name__ == '__main__':
    try:    
        motion_detection()
    except KeyboardInterrupt:
        print("Stopping motion detection.")
    finally:
        cap.release()
        if out_1 is not None and out_0 is not None:
            out_1.release()
            out_0.release()
        cv2.destroyAllWindows()
        print("Closing camera and resetting...")
