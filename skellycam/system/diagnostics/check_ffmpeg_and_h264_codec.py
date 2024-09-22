import subprocess

def check_ffmpeg():
    try:
        output = subprocess.check_output(['ffmpeg', '-version'], stderr=subprocess.STDOUT)
        print("FFmpeg is installed.")
    except subprocess.CalledProcessError as e:
        print("FFmpeg is not installed or not accessible.")
        return False
    return True

def check_h264_support():
    try:
        output = subprocess.check_output(['ffmpeg', '-codecs'], stderr=subprocess.STDOUT)
        if b'libx264' in output:
            print("H.264 codec (libx264) is available.")
            return True
        else:
            print("H.264 codec (libx264) is not available.")
            return False
    except subprocess.CalledProcessError as e:
        print("Error checking FFmpeg codecs:", e.output.decode())
        return False

if __name__ == "__main__":
    if check_ffmpeg() and check_h264_support():
        print("System is properly configured for H.264 encoding.")
    else:
        print("System is not properly configured for H.264 encoding.")