from manim import *
import json
import os
from pydub import AudioSegment


class SynchronizedLesson(Scene):
    """Manim scene with audio-synchronized timing"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.audio_timings = self.load_audio_timings()
        self.current_time = 0
    
    def load_audio_timings(self):
        """Load audio timing data from centralized assets folder"""
        timing_path = os.path.join("generated_contents", "video_assets", "narration_full_timing.json")
        if os.path.exists(timing_path):
            with open(timing_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def get_section_duration(self, section_name):
        """Get the audio duration for a specific section"""
        for timing in self.audio_timings:
            if timing['section'] == section_name:
                return timing['audio_duration']
        return 2.0  # Default fallback
    
    def construct(self):
        # Load the specification from centralized assets folder
        spec_path = os.path.join("generated_contents", "video_assets", "lesson_spec.json")
        if not os.path.exists(spec_path):
            title = Text("Error: No spec found", color=RED)
            self.add(title)
            return

        with open(spec_path, "r", encoding="utf-8") as f:
            spec = json.load(f)

        # 1. Opening Title Sequence
        self.play_title_sequence(spec.get("title", "Untitled"), spec.get("subtitle", ""))

        # 2. Render Sections
        for idx, section in enumerate(spec.get("sections", [])):
            section_type = section.get("type")
            section_name = f"{section_type}_{idx}"
            self.render_section(section, section_name)
            self.clear_screen()

        # 3. Closing
        self.play_closing()

    def play_title_sequence(self, title_text, subtitle_text):
        """Title with synchronized timing"""
        duration = self.get_section_duration("title")
        
        # Optimized for portrait mode
        title = Text(title_text, font_size=72, color=BLUE, width=9).to_edge(UP, buff=0.5)
        subtitle = Text(subtitle_text, font_size=38, color=WHITE, width=9).next_to(title, DOWN, buff=0.3)

        # Animate title appearance
        self.play(Write(title), run_time=1.5)
        self.play(FadeIn(subtitle, shift=UP), run_time=1.0)
        
        # Wait for audio to complete
        remaining_time = max(0, duration - 2.5)
        if remaining_time > 0:
            self.wait(remaining_time)
        
        self.play(FadeOut(subtitle), title.animate.scale(0.7).to_corner(UL), run_time=0.8)
        self.curr_title = title

    def render_section(self, section, section_name):
        """Render section with audio-synchronized timing"""
        stype = section.get("type")
        duration = self.get_section_duration(section_name)
        
        if stype == "bullet_list":
            self.render_bullet_list(section, duration)
        elif stype == "statement":
            self.render_statement(section, duration)
        elif stype == "definition":
            self.render_definition(section, duration)
        elif stype == "analogy":
            self.render_analogy(section, duration)
        elif stype == "process":
            self.render_process(section, duration)

    def render_bullet_list(self, section, audio_duration):
        """Bullet list with synchronized timing"""
        heading = Text(section.get("heading", ""), font_size=48, color=YELLOW, width=9).to_edge(UP, buff=1.5)
        items = section.get("items", [])
        
        # Animate heading
        self.play(Write(heading), run_time=1.0)
        
        # Create bullet items
        mobjects = VGroup()
        for item in items:
            bullet = Text(" " + item, font_size=36, color=WHITE, width=8.5)
            mobjects.add(bullet)
        
        mobjects.arrange(DOWN, aligned_edge=LEFT, buff=0.6).next_to(heading, DOWN, buff=0.8, aligned_edge=LEFT).shift(RIGHT * 0.5)
        
        # Calculate time per item
        time_used = 1.0  # heading time
        time_remaining = audio_duration - time_used - 0.5  # leave 0.5s buffer
        time_per_item = time_remaining / len(items) if items else 1.0
        
        # Animate each item
        for mob in mobjects:
            self.play(FadeIn(mob, shift=RIGHT * 0.5), run_time=min(0.8, time_per_item * 0.4))
            # Wait for narration of this item
            self.wait(max(0.2, time_per_item * 0.6))
        
        # Final pause
        self.wait(0.5)
        self.play(FadeOut(heading, mobjects), run_time=0.5)

    def render_statement(self, section, audio_duration):
        """Statement with synchronized timing"""
        text = section.get("text", "")
        stmt = Text(text, font_size=42, t2c={"important": YELLOW}, width=9)
        
        # Animate appearance
        write_time = min(2.0, audio_duration * 0.4)
        self.play(Write(stmt), run_time=write_time)
        
        # Wait for audio to complete
        wait_time = max(0, audio_duration - write_time - 0.5)
        if wait_time > 0:
            self.wait(wait_time)
        
        self.play(FadeOut(stmt), run_time=0.5)

    def render_definition(self, section, audio_duration):
        """Definition with synchronized timing"""
        term = Text(section.get("term", ""), font_size=56, color=GREEN, width=9).to_edge(UP, buff=2)
        definition = Text(section.get("text", ""), font_size=38, width=9).next_to(term, DOWN, buff=0.5)
        
        # Animate term
        self.play(Write(term), run_time=1.0)
        self.wait(0.5)
        
        # Animate definition
        self.play(FadeIn(definition), run_time=1.0)
        
        # Wait for audio to complete
        time_used = 2.5
        wait_time = max(0, audio_duration - time_used - 0.5)
        if wait_time > 0:
            self.wait(wait_time)
        
        self.play(FadeOut(term, definition), run_time=0.5)

    def render_analogy(self, section, audio_duration):
        """Analogy with synchronized timing (vertical layout)"""
        concept = Text(section.get("concept", ""), font_size=40, color=BLUE, width=9).shift(UP * 2)
        analogy = Text(section.get("analogy", ""), font_size=40, color=ORANGE, width=9).shift(DOWN * 2)
        arrow = Arrow(concept.get_bottom(), analogy.get_top(), buff=0.3)
        
        # Animate concept
        self.play(FadeIn(concept), run_time=1.0)
        self.wait(0.5)
        
        # Animate arrow and analogy
        self.play(GrowArrow(arrow), run_time=0.8)
        self.play(FadeIn(analogy), run_time=1.0)
        
        # Wait for audio to complete
        time_used = 3.3
        wait_time = max(0, audio_duration - time_used - 0.5)
        if wait_time > 0:
            self.wait(wait_time)
        
        self.play(FadeOut(concept, analogy, arrow), run_time=0.5)

    def render_process(self, section, audio_duration):
        """Process steps with synchronized timing (vertical layout)"""
        steps_data = section.get("steps", [])
        if not steps_data:
            return
        
        # Extract step texts
        steps_text = []
        for s in steps_data:
            if isinstance(s, dict):
                steps_text.append(s.get("text", s.get("step", str(s))))
            else:
                steps_text.append(str(s))
        
        # Create step mobjects (vertical arrangement)
        mobs = VGroup(*[Text(txt, font_size=36, width=8.5) for txt in steps_text])
        mobs.arrange(DOWN, buff=0.8)
        
        # Create arrows
        arrows = VGroup()
        for i in range(len(mobs) - 1):
            arrow = Arrow(mobs[i].get_bottom(), mobs[i+1].get_top(), buff=0.2)
            arrows.add(arrow)
        
        group = VGroup(mobs, arrows).move_to(ORIGIN)
        
        # Calculate time per step
        time_per_step = (audio_duration - 0.5) / len(mobs) if mobs else 1.0
        
        # Animate each step
        for i, mob in enumerate(mobs):
            self.play(FadeIn(mob, shift=UP), run_time=min(0.8, time_per_step * 0.4))
            if i < len(arrows):
                self.play(GrowArrow(arrows[i]), run_time=min(0.5, time_per_step * 0.3))
            # Wait for narration
            self.wait(max(0.3, time_per_step * 0.3))
        
        self.wait(0.5)
        self.play(FadeOut(group), run_time=0.5)

    def clear_screen(self):
        """Keep title, clear everything else"""
        mobs = [m for m in self.mobjects if m != self.curr_title]
        if mobs:
            self.play(FadeOut(*mobs), run_time=0.3)

    def play_closing(self):
        """Closing with synchronized timing"""
        duration = self.get_section_duration("closing")
        
        self.play(FadeOut(self.curr_title), run_time=0.5)
        thanks = Text("Thanks for Watching!", font_size=56, color=BLUE, width=9)
        
        self.play(Write(thanks), run_time=1.5)
        
        # Wait for audio to complete
        wait_time = max(0, duration - 2.0)
        if wait_time > 0:
            self.wait(wait_time)
        
        self.play(FadeOut(thanks), run_time=0.5)
