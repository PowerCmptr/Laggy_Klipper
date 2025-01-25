import time
import subprocess
import requests
from PIL import Image, ImageDraw, ImageFont
import RPi.GPIO as GPIO
import threading

# GPIO Knobs
CLK = 13  # encoder A
DT = 26  # encoder B
BUTTON = 19  # click

# Framebuffer device
FRAMEBUFFER = "/dev/fb0"

# Image paths
OPEN_MOUTH = "open-mouth.png"
CLOSED_MOUTH = "closed-mouth.png"
SLEEPY = "sleepy.png"
WORKING = "working.png"

# Screen dimensions
WIDTH = 320
HEIGHT = 240

# Moonraker
MOONRAKER_URL = "http://localhost:7125/"

# Set up GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(CLK, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(DT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Variables
last_state = GPIO.input(CLK)  # Read initial state
counter = 0
last_button_press_time = 0
double_click_threshold = 0.5  # seconds
current_speed = 100  # Initial speed set to 100%
last_knob_turn_time = 0  # Timestamp of the last knob turn
knob_timeout = 0.5  # Timeout in seconds
left_turn_counter = 0  # Counter for left turns
single_click_detected = False  # Flag to track single click
double_click_detected = False  # Flag to track double click
double_click_processed = False  # Flag to track if double click has been processed
last_input_time = time.time()  # Timestamp of the last input
task_bar_displayed = False  # Flag to track if the task bar is displayed
mcu_connected = True  # Flag to track if the MCU is connected
mcu_startup = False  # Flag to track if the MCU is starting up

# Font settings
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_SIZE = 20

def clear_framebuffer():
    """Clears the framebuffer to prevent artifacts."""
    framebuffer_size = WIDTH * HEIGHT * 4  # 32-bit color depth, 4 bytes per pixel
    with open(FRAMEBUFFER, "wb") as fb:
        fb.write(b'\x00' * framebuffer_size)  # Clears screen for 32-bit mode (all black)

def convert_to_rgb(image):
    """Converts an image to RGB (32-bit color)."""
    return image.convert("RGB")  # Convert to RGB (3 bytes per pixel)

def display_image(image_path, text=None):
    """Displays an image on the framebuffer with correct formatting and optional text."""
    img = Image.open(image_path)
    img = img.resize((WIDTH, HEIGHT - 60))  # Resize to match framebuffer resolution, leaving space for text
    img = convert_to_rgb(img)  # Convert to RGB (32-bit color)

    framebuffer_data = bytearray()
    
    for y in range(HEIGHT - 60):
        for x in range(WIDTH):
            r, g, b = img.getpixel((x, y))  # Get RGB values
            # Pack pixel in 32-bit (RGBA format)
            framebuffer_data.append(b)  # Blue channel
            framebuffer_data.append(g)  # Green channel
            framebuffer_data.append(r)  # Red channel
            framebuffer_data.append(0)  # Alpha channel (0 for fully transparent)

    # Create an image for the text
    text_img = Image.new("RGB", (WIDTH, 60), (0, 0, 0))
    draw = ImageDraw.Draw(text_img)
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    if text:
        draw.text((10, 10), text, font=font, fill=(255, 255, 255))

    # Add text image to framebuffer data
    for y in range(60):
        for x in range(WIDTH):
            r, g, b = text_img.getpixel((x, y))  # Get RGB values
            framebuffer_data.append(b)  # Blue channel
            framebuffer_data.append(g)  # Green channel
            framebuffer_data.append(r)  # Red channel
            framebuffer_data.append(0)  # Alpha channel (0 for fully transparent)

    # Write to framebuffer
    with open(FRAMEBUFFER, "wb") as fb:
        fb.write(framebuffer_data)

def speak_with_animation(text):
    """Speaks the text while animating the mouth images."""
    clear_framebuffer()  # Clear screen before speaking
    process = subprocess.Popen(["espeak", text], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Animate mouth while speaking
    while process.poll() is None:  # While espeak is running
        display_image(OPEN_MOUTH, text)
        time.sleep(0.2)
        display_image(CLOSED_MOUTH, text)
        time.sleep(0.2)

    # After speaking, keep mouth closed
    display_image(CLOSED_MOUTH, text)

def get_printer_status():
    """Fetches the printer status and print percentage from Moonraker."""
    global mcu_connected, mcu_startup  # Add this line to declare the variables as global
    try:
        # Query the printer state
        response = requests.get(f"{MOONRAKER_URL}printer/objects/query?print_stats")
        response.raise_for_status()
        data = response.json()
        status = data.get("result", {}).get("status", {}).get("print_stats", {}).get("state", "unknown")
        print(f"Printer status: {status}")  # Debugging statement

        # Query the print progress
        response = requests.get(f"{MOONRAKER_URL}printer/objects/query?virtual_sdcard")
        response.raise_for_status()
        data = response.json()
        progress = data.get("result", {}).get("status", {}).get("virtual_sdcard", {}).get("progress", 0)
        progress_percentage = round(progress * 100, 2)  # Convert to percentage and round to 2 decimal places
        print(f"Print progress: {progress_percentage}%")  # Debugging statement

        # Query the MCU status
        response = requests.get(f"{MOONRAKER_URL}printer/info")
        response.raise_for_status()
        data = response.json()
        mcu_status = data.get("result", {}).get("state", "unknown")
        print(f"MCU status: {mcu_status}")  # Debugging statement

        if "error" in mcu_status:
            mcu_connected = False
            mcu_startup = False
            status = "MCU disconnected"
        elif "startup" in mcu_status:
            mcu_connected = True
            mcu_startup = True
            status = "startup"
        else:
            mcu_connected = True
            mcu_startup = False

        return status, progress_percentage, mcu_status
    except requests.RequestException as e:
        print(f"Failed to get printer status: {e}")  # Debugging statement
        return f"Failed to get printer status: {e}", None, None

def pause_or_resume_print():
    """Pauses or resumes the print based on the current state."""
    status, progress, _ = get_printer_status()
    if status == "printing":
        response = requests.post(f"{MOONRAKER_URL}printer/print/pause")
        if response.status_code == 200:
            speak_with_animation("Print paused.")
            print("Print paused.")  # Debugging statement
        else:
            speak_with_animation("Failed to pause print.")
            print("Failed to pause print.")  # Debugging statement
    elif status == "paused":
        response = requests.post(f"{MOONRAKER_URL}printer/print/resume")
        if response.status_code == 200:
            speak_with_animation("Print resumed.")
            print("Print resumed.")  # Debugging statement
        else:
            speak_with_animation("Failed to resume print.")
            print("Failed to resume print.")  # Debugging statement
    elif status == "ready":
        speak_with_animation(f"Printer is in {status} state. Print progress is {progress}%.")
        print(f"Printer is in {status} state. Print progress is {progress}%.")  # Debugging statement
    else:
        speak_with_animation(f"Printer is in {status} state.")
        print(f"Printer is in {status} state.")  # Debugging statement

def change_print_speed(increase=True):
    """Increases or decreases the print speed in 5% increments."""
    global current_speed
    print(f"Current speed before change: {current_speed}%")  # Debugging statement
    if increase:
        current_speed = min(current_speed + 5, 200)  # Cap at 200%
    else:
        current_speed = max(current_speed - 5, 10)  # Floor at 10%
    print(f"Current speed after change: {current_speed}%")  # Debugging statement
    
    response = requests.post(f"{MOONRAKER_URL}printer/gcode/script?script=M220 S{current_speed}")
    if response.status_code == 200:
        speak_with_animation(f"Print speed set to {current_speed}%.")
        print(f"Print speed set to {current_speed}%.")  # Debugging statement
    else:
        speak_with_animation("Failed to change print speed.")
        print("Failed to change print speed.")  # Debugging statement

def restart_firmware():
    """Restarts the printer firmware."""
    print("Attempting to restart firmware...")  # Debugging statement
    response = requests.post(f"{MOONRAKER_URL}printer/firmware_restart")
    print(f"Firmware restart response: {response.status_code}")  # Debugging statement
    if response.status_code == 200:
        speak_with_animation("Firmware restarted.")
        print("Firmware restarted.")  # Debugging statement
    else:
        speak_with_animation("Failed to restart firmware.")
        print("Failed to restart firmware.")  # Debugging statement

def home_all_axes():
    """Homes all axes of the printer."""
    print("Homing all axes...")  # Debugging statement
    response = requests.post(f"{MOONRAKER_URL}printer/gcode/script?script=G28")
    print(f"Home all axes response: {response.status_code}")  # Debugging statement
    if response.status_code == 200:
        speak_with_animation("Homing all axes.")
        print("Homing all axes.")  # Debugging statement
    else:
        speak_with_animation("Failed to home all axes.")
        print("Failed to home all axes.")  # Debugging statement

def clear_print_stats():
    """Clears the printer's print stats."""
    print("Clearing print stats...")  # Debugging statement
    response = requests.post(f"{MOONRAKER_URL}printer/print/clear")
    print(f"Clear print stats response: {response.status_code}")  # Debugging statement
    if response.status_code == 200:
        speak_with_animation("Print stats cleared.")
        print("Print stats cleared.")  # Debugging statement
    else:
        speak_with_animation("Failed to clear print stats.")
        print("Failed to clear print stats.")  # Debugging statement

def knob_callback(channel):
    """Callback function for knob rotation."""
    global last_state, last_knob_turn_time, left_turn_counter, last_input_time, task_bar_displayed
    current_time = time.time()
    last_input_time = current_time  # Update last input time
    task_bar_displayed = False  # Reset task bar flag

    if current_time - last_knob_turn_time < knob_timeout:
        return  # Ignore if within timeout period

    current_state = GPIO.input(CLK)
    dt_state = GPIO.input(DT)
    if current_state != last_state:
        if dt_state != current_state:
            print("Knob turned right.")  # Debugging statement
            change_print_speed(increase=True)
            left_turn_counter = 0  # Reset left turn counter
        else:
            print("Knob turned left.")  # Debugging statement
            left_turn_counter += 1
            if left_turn_counter >= 2:
                change_print_speed(increase=False)
                left_turn_counter = 0  # Reset left turn counter after decreasing speed
        last_state = current_state
        last_knob_turn_time = current_time  # Update the last knob turn time

def button_callback(channel):
    """Callback function for button press."""
    global last_button_press_time, single_click_detected, double_click_detected, double_click_processed, last_input_time, task_bar_displayed
    current_time = time.time()
    last_input_time = current_time  # Update last input time
    task_bar_displayed = False  # Reset task bar flag

    if current_time - last_button_press_time < double_click_threshold:
        print("Double click detected.")  # Debugging statement
        single_click_detected = False  # Reset single click flag
        double_click_detected = True  # Set double click flag
        double_click_processed = True  # Set double click processed flag
        status, _, _ = get_printer_status()
        if status == "complete":
            double_click_action()
        else:
            pause_or_resume_print()  # This function already handles speaking the appropriate message
    else:
        last_button_press_time = current_time
        single_click_detected = True
        double_click_detected = False  # Reset double click flag
        double_click_processed = False  # Reset double click processed flag
        # Use a timer to check for double click instead of sleep
        threading.Timer(double_click_threshold, check_single_click).start()

def check_single_click():
    global single_click_detected, double_click_detected, double_click_processed
    if single_click_detected and not double_click_detected and not double_click_processed:
        single_click_detected = False  # Reset single click flag
        try:
            status, progress, mcu_status = get_printer_status()
            if mcu_connected == False:
                speak_with_animation("MCU disconnected. Restarting firmware...")
                print("MCU not found. Restarting firmware...")  # Debugging statement
                restart_firmware()
            else:
                if mcu_startup == True:
                    speak_with_animation("MCU is starting up. Please wait.")
                    print("MCU is starting up. Please wait.")  # Debugging statement
                    display_image(CLOSED_MOUTH, "MCU is starting up...")
                elif status == "printing":
                    speak_with_animation(f"Print progress is {progress}%.")
                    print(f"Print progress is {progress}%.")  # Debugging statement
                elif status == "ready":
                    speak_with_animation("Status: Ready")
                    print("Status: Ready")  # Debugging statement
                    display_image(SLEEPY, "Status: Ready")
                elif status == "standby" and mcu_startup == False and mcu_connected == True:
                    speak_with_animation("Status: Standby")
                    print("Status: Standby")  # Debugging statement
                    display_image(SLEEPY, "Status: Standby")
                elif status == "complete":
                    speak_with_animation("Status: Complete")
                    print("Status: Complete")  # Debugging statement
                    display_image(WORKING, "Status: Complete")
                else:
                    speak_with_animation(f"The printer status is {status}.")
                    print(f"The printer status is {status}.")  # Debugging statement
        except requests.RequestException as e:
            print(f"Error: {e}")  # Debugging statement

def display_task_bar():
    """Displays the task bar with current progress, speed, and status."""
    global task_bar_displayed
    status, progress, _ = get_printer_status()
    if status == "ready":
        text = "Status: Ready"
        display_image(SLEEPY, text)
    elif status == "MCU disconnected":
        text = "MCU disconnected."
        display_image(CLOSED_MOUTH, text)
    elif status == "startup":
        text = "MCU is starting up..."
        display_image(CLOSED_MOUTH, text)
    elif status == "standby":
        text = "Status: Standby"
        display_image(SLEEPY, text)
    elif status == "complete":
        text = "Status: Complete"
        display_image(WORKING, text)
    else:
        text = f"%: {progress}  S: {current_speed}  T: {status}"
        display_image(CLOSED_MOUTH, text)
    task_bar_displayed = True
    threading.Timer(5, display_task_bar).start()  # Refresh task bar every 5 seconds

def check_for_task_bar():
    """Checks if the task bar should be displayed."""
    global last_input_time, task_bar_displayed
    current_time = time.time()
    if current_time - last_input_time > 10 and not task_bar_displayed:
        display_task_bar()
    threading.Timer(1, check_for_task_bar).start()  # Check every second

def double_click_action():
    """Action to perform on double click when status is complete."""
    global task_bar_displayed
    restart_firmware()
    display_image(WORKING, "Restarting firmware...")
    time.sleep(10)  # Wait for 10 seconds
    home_all_axes()
    clear_print_stats()
    display_image(WORKING, "Homing all axes")
    task_bar_displayed = False  # Reset task bar flag

# Add event detection for button press and knob rotation
GPIO.add_event_detect(BUTTON, GPIO.FALLING, callback=button_callback, bouncetime=300)
GPIO.add_event_detect(CLK, GPIO.BOTH, callback=knob_callback, bouncetime=50)

# Start checking for task bar display
check_for_task_bar()

# Main loop
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    GPIO.cleanup()