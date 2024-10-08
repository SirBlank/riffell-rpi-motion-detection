import numpy as np
import cv2
from time import sleep, time
from threading import Thread, Event
from picamera2 import Picamera2, Preview
from picamera2.encoders import H264Encoder
from picamera2.outputs import CircularOutput
import gpiozero

# GPIO setup
input_pin = gpiozero.InputDevice(22)
output_pin = gpiozero.OutputDevice(17)

# Define image size
lsize = (640, 480)
picam2 = Picamera2()

video_config = picam2.create_video_configuration(main={"size": (1456, 1088), "format": "RGB888"}, lores={"size": lsize, "format": "YUV420"})
picam2.configure(video_config)
picam2.start_preview(Preview.QT)
encoder = H264Encoder(1000000, repeat=True)
encoder.output = CircularOutput()
picam2.start()
picam2.start_encoder(encoder)

def detect_motion(frame, back_sub, kernel, min_contour_area):
    fg_mask = back_sub.apply(frame)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
    fg_mask = cv2.medianBlur(fg_mask, 5)
    _, fg_mask = cv2.threshold(fg_mask, 127, 255, cv2.THRESH_BINARY)

    contours, _ = cv2.findContours(fg_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    areas = [cv2.contourArea(c) for c in contours]

    if len(areas) > 0:
        max_index = np.argmax(areas)
        if areas[max_index] > min_contour_area:
            return contours[max_index]
    return None

def motion_detection(stop_event, back_sub, kernel, min_contour_area):
    prev_x = None
    while not stop_event.is_set():
        frame = picam2.capture_array()
        contour = detect_motion(frame, back_sub, kernel, min_contour_area)
        
        if contour is not None:
            x, y, w, h = cv2.boundingRect(contour)
            x2 = x + int(w / 2)
            y2 = y + int(h / 2)

            if prev_x is not None and x2 < prev_x:
                print("Motion Detected! Sending signal...")
                output_pin.on()
                sleep(0.5)
                output_pin.off()

            prev_x = x2

def signal_listener(stop_event):
    while not stop_event.is_set():
        if input_pin.is_active:
            print("Signal received from circuit, saving recording.")
            epoch = int(time())
            encoder.output.fileoutput = f"{epoch}.h264"
            encoder.output.start()
            sleep(10)
            encoder.output.stop()
            print(f"Saved video as {epoch}.h264.")
            break
        sleep(0.1)

try:
    print("Starting motion detection and signal listening. Press Ctrl+C to stop.")
    sleep(5)

    stop_event = Event()
    back_sub = cv2.createBackgroundSubtractorMOG2(history=700, varThreshold=50, detectShadows=True)
    kernel = np.ones((30, 30), np.uint8)
    min_contour_area = 1000

    motion_thread = Thread(target=motion_detection, args=(stop_event, back_sub, kernel, min_contour_area))
    signal_thread = Thread(target=signal_listener, args=(stop_event,))

    motion_thread.start()
    signal_thread.start()

    motion_thread.join()
    signal_thread.join()

except KeyboardInterrupt:
    print("Stopping motion detection and signal listening.")
finally:
    stop_event.set()
    motion_thread.join()
    signal_thread.join()
    picam2.stop_encoder()
    picam2.stop()
    input_pin.close()
    output_pin.close()
    print("Closing pins and resetting...")
