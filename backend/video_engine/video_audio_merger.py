import subprocess
import os
import json


class VideoAudioMerger:
    """Handles merging video and audio using FFmpeg"""
    
    def __init__(self, video_path, audio_path, output_path="final_video.mp4"):
        self.video_path = video_path
        self.audio_path = audio_path
        self.output_path = output_path
    
    def check_ffmpeg(self):
        """Check if FFmpeg is installed"""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                check=True
            )
            print(" FFmpeg is installed")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(" FFmpeg not found!")
            print("Please install FFmpeg from: https://ffmpeg.org/download.html")
            return False
    
    def get_video_duration(self):
        """Get video duration using FFprobe"""
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                self.video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception as e:
            print(f" Could not get video duration: {e}")
            return None
    
    def get_audio_duration(self):
        """Get audio duration using FFprobe"""
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                self.audio_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception as e:
            print(f"Could not get audio duration: {e}")
            return None
    
    def merge_simple(self):
        """Simple merge: replace video audio with narration"""
        print(" Merging video and audio...")
        
        if not self.check_ffmpeg():
            return False
        
        # Get durations
        video_duration = self.get_video_duration()
        audio_duration = self.get_audio_duration()
        
        if video_duration and audio_duration:
            print(f"Video duration: {video_duration:.2f}s")
            print(f"Audio duration: {audio_duration:.2f}s")
            
            if abs(video_duration - audio_duration) > 2.0:
                print(f"Warning: Duration mismatch of {abs(video_duration - audio_duration):.2f}s")
        
        # FFmpeg command to merge
        cmd = [
            "ffmpeg",
            "-i", self.video_path,      # Input video
            "-i", self.audio_path,      # Input audio
            "-c:v", "copy",             # Copy video codec (no re-encoding)
            "-c:a", "aac",              # Encode audio to AAC
            "-b:a", "192k",             # Audio bitrate
            "-map", "0:v:0",            # Map video from first input
            "-map", "1:a:0",            # Map audio from second input
            "-shortest",                # End when shortest stream ends
            "-y",                       # Overwrite output file
            self.output_path
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            print(f"Video with audio created: {self.output_path}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg merge failed!")
            print("STDERR:", e.stderr)
            return False
    
    def merge_with_speed_adjustment(self, target_duration=None):
        """Advanced merge: adjust video speed to match audio duration"""
        print(" Merging with speed adjustment...")
        
        if not self.check_ffmpeg():
            return False
        
        video_duration = self.get_video_duration()
        audio_duration = self.get_audio_duration()
        
        if not video_duration or not audio_duration:
            print("Could not determine durations, using simple merge")
            return self.merge_simple()
        
        # Calculate speed factor
        speed_factor = video_duration / audio_duration
        
        print(f"Video duration: {video_duration:.2f}s")
        print(f"Audio duration: {audio_duration:.2f}s")
        print(f"Speed adjustment: {speed_factor:.2f}x")
        
        if 0.9 <= speed_factor <= 1.1:
            # Close enough, use simple merge
            print(" Durations are close, using simple merge")
            return self.merge_simple()
        
        # Adjust video speed to match audio
        temp_video = "temp_adjusted_video.mp4"
        
        # Step 1: Adjust video speed
        cmd_adjust = [
            "ffmpeg",
            "-i", self.video_path,
            "-filter:v", f"setpts={1/speed_factor}*PTS",
            "-an",  # Remove audio
            "-y",
            temp_video
        ]
        
        try:
            subprocess.run(cmd_adjust, capture_output=True, text=True, check=True)
            print(" Video speed adjusted")
        except subprocess.CalledProcessError as e:
            print(f"Speed adjustment failed: {e.stderr}")
            return False
        
        # Step 2: Merge adjusted video with audio
        cmd_merge = [
            "ffmpeg",
            "-i", temp_video,
            "-i", self.audio_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-y",
            self.output_path
        ]
        
        try:
            subprocess.run(cmd_merge, capture_output=True, text=True, check=True)
            print(f"Synchronized video created: {self.output_path}")
            
            # Clean up temp file
            if os.path.exists(temp_video):
                os.remove(temp_video)
            
            return True
        except subprocess.CalledProcessError as e:
            print(f"Merge failed: {e.stderr}")
            return False


def merge_video_audio(video_path, audio_path, output_path="final_video.mp4", adjust_speed=False):
    """Convenience function to merge video and audio"""
    merger = VideoAudioMerger(video_path, audio_path, output_path)
    
    if adjust_speed:
        return merger.merge_with_speed_adjustment()
    else:
        return merger.merge_simple()


if __name__ == "__main__":
    # Test with default paths
    video = "media/videos/manim_engine/480p15/GeneratedLesson.mp4"
    audio = "narration_full.mp3"
    
    if os.path.exists(video) and os.path.exists(audio):
        merge_video_audio(video, audio, "final_video_with_narration.mp4")
    else:
        print(" Video or audio file not found")
        print(f"Video: {video} - {'' if os.path.exists(video) else ''}")
        print(f"Audio: {audio} - {'' if os.path.exists(audio) else ''}")
