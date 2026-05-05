import json
import os
from gtts import gTTS
from pydub import AudioSegment
from pydub.silence import detect_silence
import asyncio
import edge_tts


class TTSGenerator:
    """Handles text-to-speech generation and audio timing"""
    
    def __init__(self, spec_path="generated_contents/video_assets/lesson_spec.json", output_dir="generated_contents/audio_segments"):
        self.spec_path = spec_path
        self.output_dir = output_dir
        self.audio_segments = []
        self.timing_data = []
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Check for FFmpeg availability
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        """Check if FFmpeg is installed and in PATH"""
        from shutil import which
        if not which("ffmpeg") and not which("avconv"):
            print("WARNING: FFmpeg not found in PATH. Audio processing will fail.")
            print("   Please install FFmpeg: winget install Gyan.FFmpeg")
    
    def load_spec(self):
        """Load the lesson specification"""
        with open(self.spec_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def generate_narration_script(self, spec):
        """Convert lesson spec into narration script with timing markers"""
        script_segments = []
        
        # Title sequence
        title = spec.get('title', 'Untitled')
        subtitle = spec.get('subtitle', '')
        
        script_segments.append({
            'section': 'title',
            'text': f"{title}. {subtitle}",
            'duration_estimate': 4.0  # 2s animation + 2s pause
        })
        
        # Process each section
        for idx, section in enumerate(spec.get('sections', [])):
            section_type = section.get('type')
            
            if section_type == 'definition':
                term = section.get('term', '')
                text = section.get('text', '')
                narration = f"{term}. {text}"
                duration = 4.5  # Write term (1s) + pause (0.5s) + definition (3s)
                
            elif section_type == 'bullet_list':
                heading = section.get('heading', '')
                items = section.get('items', [])
                narration = f"{heading}. " + ". ".join(items)
                duration = 2.0 + len(items) * 1.5  # Heading + items with pauses
                
            elif section_type == 'statement':
                narration = section.get('text', '')
                duration = 4.0
                
            elif section_type == 'analogy':
                concept = section.get('concept', '')
                analogy = section.get('analogy', '')
                narration = f"{concept} is like {analogy}"
                duration = 5.0
                
            elif section_type == 'process':
                steps = section.get('steps', [])
                # Handle both string and dict steps
                step_texts = []
                for s in steps:
                    if isinstance(s, dict):
                        step_texts.append(s.get('text', s.get('step', str(s))))
                    else:
                        step_texts.append(str(s))
                narration = ". ".join(step_texts)
                duration = 3.0 + len(steps) * 2.0
            else:
                continue
            
            script_segments.append({
                'section': f'{section_type}_{idx}',
                'text': narration,
                'duration_estimate': duration
            })
        
        # Closing
        script_segments.append({
            'section': 'closing',
            'text': 'Thanks for watching!',
            'duration_estimate': 3.0
        })
        
        return script_segments
    
    async def generate_audio_edge_tts(self, text, output_path, voice="en-US-AriaNeural"):
        """Generate audio using edge-tts (higher quality, natural voices)"""
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
    
    def generate_audio_gtts(self, text, output_path, lang='en', slow=False):
        """Generate audio using gTTS (fallback option)"""
        tts = gTTS(text=text, lang=lang, slow=slow)
        tts.save(output_path)
    
    def generate_all_audio_segments(self, script_segments, use_edge_tts=True):
        """Generate audio for all script segments"""
        print("Generating narration audio...")
        
        # Ensure output directory exists (Just-in-Time)
        os.makedirs(self.output_dir, exist_ok=True)

        for idx, segment in enumerate(script_segments):
            text = segment['text']
            section = segment['section']
            output_path = os.path.join(self.output_dir, f"segment_{idx:02d}_{section}.mp3")
            
            print(f"  [{idx+1}/{len(script_segments)}] {section}: {text[:50]}...")
            
            try:
                if use_edge_tts:
                    # Use edge-tts for better quality
                    asyncio.run(self.generate_audio_edge_tts(text, output_path))
                else:
                    # Fallback to gTTS
                    self.generate_audio_gtts(text, output_path)
                
                # Load audio to get actual duration
                audio = AudioSegment.from_mp3(output_path)
                actual_duration = len(audio) / 1000.0  # Convert to seconds
                
                self.audio_segments.append(output_path)
                self.timing_data.append({
                    'section': section,
                    'audio_file': output_path,
                    'audio_duration': actual_duration,
                    'animation_duration': segment['duration_estimate']
                })
                
            except Exception as e:
                print(f"  Warning: Error generating audio for {section}: {e}")
                # Create silent audio as fallback
                silence = AudioSegment.silent(duration=int(segment['duration_estimate'] * 1000))
                silence.export(output_path, format="mp3")
                self.audio_segments.append(output_path)
                self.timing_data.append({
                    'section': section,
                    'audio_file': output_path,
                    'audio_duration': segment['duration_estimate'],
                    'animation_duration': segment['duration_estimate']
                })
        
        print(f"Generated {len(self.audio_segments)} audio segments")
        return self.timing_data
    
    def merge_audio_segments(self, output_path="generated_contents/video_assets/narration_full.mp3", add_pauses=True):
        """Merge all audio segments into a single file with appropriate pauses"""
        print("Merging audio segments...")
        
        combined = AudioSegment.empty()
        
        for idx, timing in enumerate(self.timing_data):
            audio_file = timing['audio_file']
            audio_duration = timing['audio_duration']
            animation_duration = timing['animation_duration']
            
            # Load audio segment
            segment = AudioSegment.from_mp3(audio_file)
            
            # Add the audio
            combined += segment
            
            # Add pause if animation is longer than audio
            if add_pauses and animation_duration > audio_duration:
                pause_duration = (animation_duration - audio_duration) * 1000  # ms
                combined += AudioSegment.silent(duration=int(pause_duration))
        
        # Export merged audio
        combined.export(output_path, format="mp3")
        print(f"Merged audio saved to: {output_path}")
        
        # Save timing data
        timing_json_path = output_path.replace('.mp3', '_timing.json')
        with open(timing_json_path, 'w', encoding='utf-8') as f:
            json.dump(self.timing_data, f, indent=2)
        print(f"Timing data saved to: {timing_json_path}")
        
        return output_path, len(combined) / 1000.0  # Return path and duration in seconds
    
    def generate_full_narration(self, use_edge_tts=True):
        """Complete pipeline: spec  script  audio segments  merged audio"""
        # Load spec
        spec = self.load_spec()
        
        # Generate script
        script_segments = self.generate_narration_script(spec)
        
        # Generate audio segments
        self.generate_all_audio_segments(script_segments, use_edge_tts=use_edge_tts)
        
        # Merge segments
        audio_path, duration = self.merge_audio_segments()
        
        return audio_path, duration


def main():
    """Test the TTS generator"""
    generator = TTSGenerator()
    audio_path, duration = generator.generate_full_narration(use_edge_tts=True)
    print(f"\nComplete! Audio duration: {duration:.2f} seconds")
    print(f"Audio file: {audio_path}")


if __name__ == "__main__":
    main()
