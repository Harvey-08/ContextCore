
import React from 'react';
import { BookOpen, Brain, Sparkles, ChevronRight, CheckCircle, Video, FileText } from 'lucide-react';
import { motion } from 'framer-motion';

const FeatureCard = ({ icon: Icon, title, desc }) => (
  <div className="glass-panel p-8 flex flex-col items-center text-center hover:scale-105 transition-transform">
    <div className="w-14 h-14 bg-teal-50 text-teal-600 rounded-2xl flex items-center justify-center mb-6">
      <Icon size={28} />
    </div>
    <h3 className="text-xl font-bold text-slate-800 mb-3">{title}</h3>
    <p className="text-slate-500 text-sm leading-relaxed">{desc}</p>
  </div>
);

const LandingPage = ({ onGetStarted }) => {
  return (
    <div className="min-h-screen bg-[#f7f9fa]">
      {/* Navigation */}
      <nav className="fixed top-0 w-full z-50 px-8 py-6 flex justify-between items-center bg-white/80 backdrop-blur-md border-b border-slate-100">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-teal-500 rounded-lg flex items-center justify-center text-white font-bold">
            <BookOpen size={18} />
          </div>
          <span className="text-xl font-bold text-slate-800 tracking-tight">ContextCore</span>
        </div>
        <div className="hidden md:flex items-center gap-4 text-sm font-bold text-slate-800">
          <a href="#features" className="px-5 py-2.5 rounded-2xl bg-teal-50 text-teal-600 hover:bg-teal-100 transition-all">Features</a>
          <a href="#how-it-works" className="px-5 py-2.5 rounded-2xl bg-teal-50 text-teal-600 hover:bg-teal-100 transition-all">How it Works</a>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-40 pb-20 px-6">
        <div className="max-w-6xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <span className="px-4 py-1.5 rounded-full bg-teal-50 text-teal-600 text-xs font-bold uppercase tracking-widest mb-6 inline-block">
              AI-Powered Teaching Assistant
            </span>
            <h1 className="text-5xl md:text-7xl font-extrabold text-slate-900 mb-8 tracking-tight">
              Transform Your Curriculum <br />
              <span className="text-teal-500">Into Interactive Learning</span>
            </h1>
            <p className="text-xl text-slate-500 mb-10 max-w-2xl mx-auto leading-relaxed">
              Upload your textbook PDFs and instantly generate lesson plans, quizzes,
              flashcards, and animated videos—all perfectly aligned with your curriculum.
            </p>
            <div className="flex flex-col md:flex-row items-center justify-center gap-4">
              <button onClick={onGetStarted} className="btn-primary text-lg px-10 py-4 shadow-xl shadow-teal-500/20">
                Get Started for Free <ChevronRight size={20} />
              </button>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-10 border-y border-slate-100 bg-white">
        <div className="max-w-6xl mx-auto px-6 flex flex-wrap justify-center gap-12 md:gap-24">
          <div className="text-center">
            <div className="text-3xl font-bold text-slate-800">100%</div>
            <div className="text-sm text-slate-400 font-medium uppercase tracking-widest">Curriculum Aligned</div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-slate-800">5+</div>
            <div className="text-sm text-slate-400 font-medium uppercase tracking-widest">Content Formats</div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-slate-800">Zero</div>
            <div className="text-sm text-slate-400 font-medium uppercase tracking-widest">Manual Prep Time</div>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section id="features" className="py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-slate-800 mb-4">Everything You Need to Teach Better</h2>
            <p className="text-slate-500 max-w-xl mx-auto">Automate the boring stuff and focus on your students. Our AI handles the prep so you can handle the class.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <FeatureCard
              icon={Sparkles}
              title="Level-Appropriate"
              desc="AI ensures all explanations and questions are perfectly suited for the specific grade level of the textbook."
            />
            <FeatureCard
              icon={Brain}
              title="Smart Quizzes"
              desc="Generate multiple-choice and short-answer questions with instant feedback and PDF export options."
            />
            <FeatureCard
              icon={Video}
              title="Animated Lessons"
              desc="Transform static textbook paragraphs into dynamic animated videos with synchronized AI narration."
            />
          </div>
        </div>
      </section>

      {/* How it Works */}
      <section id="how-it-works" className="py-24 px-6 bg-white border-t border-slate-100 relative">
        <div className="max-w-6xl mx-auto relative z-10">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-slate-800 mb-4">Simplified Content Workflow</h2>
            <p className="text-slate-500 max-w-xl mx-auto">Three simple steps to transform your static curriculum into high-quality educational content.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
            <div className="flex flex-col items-center text-center">
              <div className="w-12 h-12 bg-teal-500 rounded-full flex items-center justify-center font-bold text-xl text-white mb-6 shadow-lg shadow-teal-500/20">1</div>
              <h3 className="text-xl font-bold text-slate-800 mb-3">Upload PDF</h3>
              <p className="text-slate-500 text-sm">Upload your NCERT chapter or textbook PDF to the dashboard.</p>
            </div>
            <div className="flex flex-col items-center text-center">
              <div className="w-12 h-12 bg-teal-500 rounded-full flex items-center justify-center font-bold text-xl text-white mb-6 shadow-lg shadow-teal-500/20">2</div>
              <h3 className="text-xl font-bold text-slate-800 mb-3">Select Topic</h3>
              <p className="text-slate-500 text-sm">Choose a specific topic from the automatically extracted curriculum list.</p>
            </div>
            <div className="flex flex-col items-center text-center">
              <div className="w-12 h-12 bg-teal-500 rounded-full flex items-center justify-center font-bold text-xl text-white mb-6 shadow-lg shadow-teal-500/20">3</div>
              <h3 className="text-xl font-bold text-slate-800 mb-3">Generate & Download</h3>
              <p className="text-slate-500 text-sm">Select your format (Plan, Quiz, Video) and get your content in seconds.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Simple Footer */}
      <footer className="py-12 border-t border-slate-100 bg-white">
        <div className="max-w-6xl mx-auto px-6 text-center text-slate-400 text-sm">
          © 2026 ContextCore AI. All rights reserved.
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
