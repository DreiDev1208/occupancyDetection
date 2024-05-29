import cv2
import numpy as np
import time
import paho.mqtt.client as mqtt
import certifi

MQTT_USERNAME = "IotDevice001"
MQTT_PASS = "andreimar123"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected successfully.")
    else:
        print("Connection failed with error code %d." % rc)

def on_publish(client, userdata, mid):
    print("Message published.")

def detect_vertical_lines(frame):
    # Create a copy of the frame
    frame_copy = frame.copy()

    # Convert frame to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # Apply Canny edge detection
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    # Apply Hough line transform
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=105, minLineLength=130, maxLineGap=40)

    if lines is not None:
        # Draw the detected lines on the frame copy
        for line in lines:
            x1, y1, x2, y2 = line[0]
            # Calculate the slope of the line
            if x2 - x1 == 0:  # To prevent division by zero
                slope = float('inf')  # Infinite slope (vertical line)
            else:
                slope = (y2 - y1) / (x2 - x1)
            # Check if the line is vertical
            if abs(slope) > 10:  # You can adjust this value as per your requirement
                cv2.line(frame_copy, (x1, y1), (x2, y2), (0, 255, 0), 2)
        return frame_copy, lines
    else:
        return frame_copy, None

cap = cv2.VideoCapture("http://192.168.137.156")
# cap = cv2.VideoCapture(0)

state_line1 = "Visible"
state_line2 = "Visible"

in_var = 0
out_var = 0

occupancy = in_var - out_var
direction = "none"

# Initialize the MQTT client
client = mqtt.Client()

# Set up TLS configuration with certifi certificate
client.tls_set(certifi.where())
client.username_pw_set(MQTT_USERNAME, password=MQTT_PASS)

client.on_connect = on_connect
client.on_publish = on_publish

# Connect to the EMQX broker
client.connect("d11986ae.ala.us-east-1.emqxsl.com", 8883, 60)

# Start the MQTT client loop
client.loop_start()

# Wait until the client is connected
while not client.is_connected():
    print("Waiting for connection...")
    time.sleep(1)

while True:
    # Capture frame-by-frame
    ret, frame = cap.read()

    # Detect vertical lines
    result_frame, lines = detect_vertical_lines(frame)

    if lines is not None:
        # Divide the frame into two sections
        height, width, _ = frame.shape
        mid_x = width // 2

        # Divide the lines into two groups based on their position
        left_lines = [line for line in lines if line[0][0] < mid_x]
        right_lines = [line for line in lines if line[0][0] >= mid_x]

        cv2.line(result_frame, (mid_x, 0), (mid_x, height), (0, 0, 255), 2)

        # Display the frames
        cv2.imshow('Frame', result_frame)

        skip_next = False

        if len(left_lines) > 0 and len(right_lines) == 0 and state_line1 == "Visible" and state_line2 == "Visible" and direction == "none":
            state_line1 = "Obstructed"
            direction = "left to right"
            print(direction)
            skip_next = True

        elif len(left_lines) == 0 and len(right_lines) > 0 and state_line1 == "Obstructed" and state_line2 == "Visible" and direction == "left to right":
            print("Entity finished moving from left to right!")
            out_var += 1
            occupancy = in_var - out_var
            print("occupancy", occupancy)
            client.publish("occupancy/vehicle", str(occupancy))  # Publish the occupancy
            state_line1 = "Visible"
            time.sleep(1.8)
            direction = "none"
            skip_next = True

        if skip_next:
            continue

        if len(right_lines) > 0 and len(left_lines) == 0 and state_line2 == "Visible" and state_line1 == "Visible" and direction == "none" and direction != "left to right":
            state_line2 = "Obstructed"
            direction = "right to left"
            print(direction)

        elif len(right_lines) == 0 and len(left_lines) > 0 and state_line2 == "Obstructed" and state_line1 == "Visible" and direction == "right to left":
            print("Entity finished moving from right to left!")
            in_var += 1
            occupancy = in_var - out_var
            print("occupancy", occupancy)
            client.publish("occupancy/vehicle", str(occupancy))  # Publish the occupancy
            state_line2 = "Visible"
            time.sleep(1.8)
            direction = "none"

    # Exit on 'q' key press
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release the capture
cap.release()
cv2.destroyAllWindows()

# Stop the MQTT client loop
client.loop_stop()

