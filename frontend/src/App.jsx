
import { useState, useEffect } from 'react'
import axios from 'axios'
import { Upload, FileText, Check, Play, BookOpen, Brain, Clock, Activity, Download, ChevronRight, X, AlertCircle, Video, MessageSquare, Send, Mic, MicOff, Volume2, Youtube } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import Dashboard from './components/Dashboard'
import QuizTaker from './components/QuizTaker'
import LandingPage from './components/LandingPage'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

// --- SUB COMPONENTS ---

const Header = ({ systemOnline, onHome }) => (
  <div className="fixed top-0 w-full glass-panel z-50 px-6 py-4 flex justify-between items-center rounded-none border-t-0 border-x-0">
    <div onClick={onHome} className="cursor-pointer group">
      <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-teal-600 to-blue-600 group-hover:opacity-80 transition-opacity" style={{ background: 'linear-gradient(to right, #14bf96, #3498db)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
        Teaching Assistant
      </h1>
      <p className="text-xs text-slate-500">AI-Powered Curriculum Content Generator</p>
    </div>
    <div className="flex items-center gap-2 bg-white px-3 py-1 rounded-full border border-slate-200 shadow-sm">
      <div className={`status-dot-active ${!systemOnline && '!bg-red-500 !animate-none'}`}></div>
      <span className="text-xs font-semibold text-slate-600">{systemOnline ? 'System Online' : 'Backend Offline'}</span>
    </div>
  </div>
)

const LandingView = ({ isProcessing, handleUpload, files, setSelectedFile, setPhase }) => (
  <div className="pt-24 min-h-screen flex items-center justify-center p-6">
    <div className="app-grid w-full">
      {/* Upload Card */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="glass-panel p-8 flex flex-col items-center justify-center text-center min-h-[400px]">
        <div className={`relative w-full h-full border-2 border-dashed border-slate-300 rounded-xl flex flex-col items-center justify-center p-6 transition-all ${isProcessing ? 'bg-slate-50' : 'hover:border-teal-400 hover:bg-slate-50'}`}>
          {isProcessing ? (
            <div className="flex flex-col items-center">
              <div className="loader-spinner mb-4"></div>
              <h3 className="text-lg font-semibold text-slate-700">Processing Document...</h3>
              <p className="text-sm text-slate-500">Extracting curriculum hierarchy</p>
            </div>
          ) : (
            <>
              <div className="w-16 h-16 bg-teal-50 text-teal-500 rounded-full flex items-center justify-center mb-4">
                <Upload size={32} />
              </div>
              <h3 className="text-xl font-semibold mb-2 text-slate-700">Upload Curriculum PDF</h3>
              <p className="text-slate-500 mb-6 max-w-xs">Drag and drop your NCERT chapter or textbook directory here.</p>
              <input type="file" onChange={handleUpload} className="hidden" id="file-upload" />
              <label htmlFor="file-upload" className="btn-primary">
                Choose File
              </label>
            </>
          )}
        </div>
      </motion.div>

      {/* Recent Files */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="flex flex-col gap-4">
        <h2 className="text-xl font-bold text-slate-700">Quick Access</h2>
        <div className="grid gap-3">
          {files.length === 0 ? (
            <div className="glass-panel p-6 text-center text-slate-400">No processed files yet.</div>
          ) : (
            files.map((f, i) => (
              <div key={i} onClick={() => { setSelectedFile(f); setPhase('dashboard'); }} className="glass-panel p-4 flex items-center gap-4 cursor-pointer hover:bg-white/50">
                <div className="w-10 h-10 bg-blue-50 text-blue-500 rounded-lg flex items-center justify-center">
                  <FileText size={20} />
                </div>
                <div className="flex-1">
                  <h4 className="font-semibold text-slate-700">{f.topics && f.topics.length > 0 ? f.topics[0] : f.filename}</h4>
                  <span className="text-xs text-slate-500">{f.topics.length} topics extracted</span>
                </div>
                <ChevronRight size={16} className="text-slate-400" />
              </div>
            ))
          )}
        </div>
      </motion.div>
    </div>
  </div>
)

const TypeCard = ({ icon, title, desc, id, selected, onSelect }) => (
  <div
    onClick={() => onSelect(id)}
    className={`p-6 rounded-xl border-2 cursor-pointer transition-all ${selected === id ? 'border-teal-400 bg-teal-50/50 shadow-md' : 'border-slate-100 hover:border-teal-200 bg-white'}`}
  >
    <div className={`w-12 h-12 rounded-lg flex items-center justify-center mb-4 ${selected === id ? 'bg-teal-100 text-teal-600' : 'bg-slate-100 text-slate-500'}`}>
      {icon}
    </div>
    <h3 className="font-bold text-slate-800 mb-1">{title}</h3>
    <p className="text-xs text-slate-500 leading-relaxed">{desc}</p>
  </div>
)

const Flashcard = ({ card }) => {
  const [isFlipped, setIsFlipped] = useState(false)

  return (
    <div
      onClick={() => setIsFlipped(!isFlipped)}
      className="relative w-full h-48 cursor-pointer perspective-1000 group dark:text-gray-800"
    >
      <motion.div
        className="w-full h-full relative preserve-3d transition-all duration-500"
        initial={false}
        animate={{ rotateY: isFlipped ? 180 : 0 }}
        transition={{ duration: 0.6, type: "spring" }}
        style={{ transformStyle: 'preserve-3d' }}
      >
        {/* Front */}
        <div className="absolute inset-0 backface-hidden bg-white border-2 border-teal-100 rounded-xl shadow-sm p-6 flex flex-col items-center justify-center text-center">
          <span className="text-xs font-bold text-teal-500 uppercase tracking-widest mb-2">{card.type}</span>
          <p className="text-lg font-medium text-slate-700">{card.front}</p>
          <p className="text-xs text-slate-400 mt-4 pt-4 border-t w-full">Click to reveal</p>
        </div>

        {/* Back */}
        <div
          className="absolute inset-0 backface-hidden bg-gradient-to-br from-teal-500 to-emerald-600 text-white rounded-xl shadow-lg p-6 flex flex-col items-center justify-center text-center"
          style={{ transform: 'rotateY(180deg)', backfaceVisibility: 'hidden' }}
        >
          <p className="text-lg font-medium">{card.back}</p>
        </div>
      </motion.div>
    </div>
  )
}

// Old Quiz component removed. Replaced by QuizTaker imported above.

const VideoGallery = ({ data }) => {
  const [activeVideo, setActiveVideo] = useState(null)

  return (
    <div className="w-full">
      <h3 className="text-2xl font-bold text-slate-800 mb-6 flex items-center gap-2">
        <Youtube className="text-red-600" />
        Videos for "{data?.query ? data.query.replace('Class 7 Math ', '').replace(' explanation', '') : 'Selected Topic'}"
      </h3>

      {activeVideo && (
        <div className="mb-8 bg-black rounded-xl overflow-hidden aspect-video shadow-2xl relative">
          <iframe
            src={activeVideo.embed_url + "?autoplay=1"}
            className="w-full h-full"
            frameBorder="0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            title="Video Player"
          ></iframe>
          <button
            onClick={() => setActiveVideo(null)}
            className="absolute top-4 right-4 bg-white/10 hover:bg-white/20 text-white p-2 rounded-full backdrop-blur-sm transition-all"
          >
            <X size={20} />
          </button>
        </div>
      )}

      {data.error ? (
        <div className="text-red-500 bg-red-50 p-4 rounded-lg flex items-center gap-2">
          <AlertCircle size={20} /> {data.error}
        </div>
      ) : (data.videos || []).length === 0 ? (
        <div className="text-slate-500 italic p-4">No videos found.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {(data.videos || []).map((vid) => (
            <div
              key={vid.id}
              onClick={() => setActiveVideo(vid)}
              className={`group bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden cursor-pointer transition-all hover:shadow-lg hover:-translate-y-1 ${activeVideo?.id === vid.id ? 'ring-2 ring-red-500' : ''}`}
            >
              <div className="relative aspect-video bg-slate-100 overflow-hidden">
                <img src={vid.thumbnail} alt={vid.title} className="w-full h-full object-cover transition-transform group-hover:scale-105" />
                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
                  <div className="w-12 h-12 bg-red-600 text-white rounded-full flex items-center justify-center shadow-lg opacity-90 scale-90 group-hover:scale-100 transition-all">
                    <Play size={20} fill="currentColor" />
                  </div>
                </div>
              </div>
              <div className="p-4">
                <h4 className="font-bold text-slate-800 line-clamp-2 mb-1 group-hover:text-red-700 transition-colors">{vid.title}</h4>
                <p className="text-xs font-medium text-slate-400">{vid.channel}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const DashboardView = ({ setPhase, selectedFile, selectedTopicIndex, setSelectedTopicIndex, selectedType, setSelectedType, handleGenerate }) => (
  <div className="pt-24 px-6 max-w-6xl mx-auto pb-20">
    <div className="flex justify-between items-center mb-6">
      <button onClick={() => setPhase('landing')} className="text-slate-500 hover:text-teal-600 flex items-center gap-1 text-sm font-medium"> Back to Upload</button>
      <div className="flex gap-2">
        <button onClick={() => { setSelectedType('youtube'); handleGenerate('youtube'); }} className="btn-secondary flex items-center gap-2 text-red-600 hover:bg-red-50 border-red-200">
          <Youtube size={18} /> Find Videos
        </button>
        <button onClick={() => setPhase('dashboard-analytics')} className="btn-secondary flex items-center gap-2">
          <Activity size={18} /> View Analytics
        </button>
      </div>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
      {/* Configuration Sidebar */}
      <div className="md:col-span-1 space-y-6">
        <motion.div initial={{ x: -20, opacity: 0 }} animate={{ x: 0, opacity: 1 }} className="glass-panel p-6">
          <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-4">Active Document</h3>
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 bg-teal-100 text-teal-600 rounded-lg flex items-center justify-center">
              <FileText size={20} />
            </div>
            <div className="overflow-hidden">
              <div className="font-bold text-slate-700 truncate">{selectedFile?.display_name || selectedFile?.filename}</div>
              <div className="text-xs text-slate-500">{selectedFile?.topic_count} topics available</div>
            </div>
          </div>

          <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-4">Select Topic</h3>
          <div className="space-y-2 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
            {selectedFile?.topics.map((topic, idx) => (
              <div
                key={idx}
                onClick={() => setSelectedTopicIndex(idx)}
                className={`p-3 rounded-lg cursor-pointer transition-all border ${selectedTopicIndex === idx ? 'bg-teal-50 border-teal-200 text-teal-700 shadow-sm' : 'hover:bg-white border-transparent text-slate-600'}`}
              >
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${selectedTopicIndex === idx ? 'bg-teal-500' : 'bg-slate-300'}`}></span>
                  <span className="text-sm font-medium">{topic}</span>
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Main Action Area */}
      <div className="md:col-span-2 space-y-6">
        <motion.div initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} className="glass-panel p-8">
          <h2 className="text-2xl font-bold text-slate-800 mb-2">What would you like to generate?</h2>
          <p className="text-slate-500 mb-8">Select a content type to generate AI-powered materials for the selected topic.</p>

          <div className="grid grid-cols-2 gap-4">
            <TypeCard
              icon={<BookOpen size={24} />}
              title="Teaching Plan"
              desc="Step-by-step lesson plan with objectives & timing."
              id="plan"
              selected={selectedType}
              onSelect={setSelectedType}
            />
            <TypeCard
              icon={<Activity size={24} />}
              title="Quiz"
              desc="Multiple choice & short answer questions."
              id="quiz"
              selected={selectedType}
              onSelect={setSelectedType}
            />
            <TypeCard
              icon={<Brain size={24} />}
              title="Practice Exercises"
              desc="Homework problems and application questions."
              id="practice"
              selected={selectedType}
              onSelect={setSelectedType}
            />
            <TypeCard
              icon={<Clock size={24} />}
              title="Flashcards"
              desc="Smart concept review cards."
              id="flashcards"
              selected={selectedType}
              onSelect={setSelectedType}
            />
            <TypeCard
              icon={<Video size={24} />}
              title="Video Lesson"
              desc="AI-generated animated video lesson (Landscape)"
              id="video"
              selected={selectedType}
              onSelect={setSelectedType}
            />
          </div>

          <div className="mt-8 flex justify-end">
            <button
              onClick={() => handleGenerate()}
              disabled={!selectedType}
              className={`btn-primary text-lg px-8 py-3 ${!selectedType && 'opacity-50 cursor-not-allowed'}`}
            >
              Generate Content &nbsp;
            </button>
          </div>
        </motion.div>
      </div>
    </div>
  </div>
)

const GeneratingView = ({ processingText }) => (
  <div className="fixed inset-0 bg-white/80 backdrop-blur-md z-50 flex flex-col items-center justify-center">
    <div className="loader-spinner mb-8"></div>
    <h2 className="text-2xl font-bold text-slate-800 mb-2">Generating Content...</h2>
    <p className="text-slate-500">{processingText || "Consulting AI models and formatting your document"}</p>

    <div className="mt-8 text-sm text-slate-400 flex flex-col gap-2 items-start">
      <div className="flex items-center gap-2 text-teal-600"><Check size={16} /> Extracted context</div>
      <div className="flex items-center gap-2 text-teal-600"><Check size={16} /> Verified facts</div>
      <div className="flex items-center gap-2 animate-pulse"><div className="w-4 h-4 rounded-full border-2 border-teal-500 border-t-transparent animate-spin"></div> Formatting output</div>
    </div>
  </div>
)

const ResultsView = ({ selectedType, selectedFile, selectedTopicIndex, generationResult, setPhase }) => (
  <div className="pt-24 px-6 max-w-4xl mx-auto pb-20 text-center">
    <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="glass-panel p-10">
      <div className="w-20 h-20 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto mb-6">
        <Check size={40} />
      </div>
      <h2 className="text-3xl font-bold text-slate-800 mb-4">Content Ready!</h2>
      <p className="text-slate-500 mb-8 max-w-md mx-auto">
        Your <b>{selectedType}</b> for <i>{selectedFile?.topics[selectedTopicIndex]}</i> has been successfully generated.
      </p>

      {generationResult?.type === 'flashcards' ? (
        <div className="mb-8">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {generationResult.data.data.cards.map((card, i) => (
              <Flashcard key={i} card={card} />
            ))}
          </div>
          <button onClick={() => {
            const blob = new Blob([JSON.stringify(generationResult.data.data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `flashcards.json`;
            a.click();
          }} className="btn-primary mt-8">Download JSON</button>
        </div>
      ) : (generationResult?.type === 'youtube' || generationResult?.type === 'resources') ? (
        <VideoGallery data={generationResult.type === 'resources' ? { videos: generationResult.data.data || generationResult.data } : generationResult.data} />
      ) : generationResult?.type === 'quiz' ? (
        <div className="w-full">
          <QuizTaker data={generationResult.data.data} onComplete={() => setPhase('dashboard')} />
        </div>
      ) : generationResult?.type === 'video' ? (
        <div className="flex flex-col items-center gap-6">
          <div className="relative rounded-xl overflow-hidden shadow-2xl border-4 border-white bg-black w-full max-w-3xl">
            <video
              controls
              autoPlay
              className="w-full h-auto block"
              src={`${API_BASE}${generationResult?.data?.file_url}`}
            >
              Your browser does not support the video tag.
            </video>
          </div>
          <a
            href={`${API_BASE}/download/${generationResult?.data?.file_url.split('/').pop()}`}
            download
            className="flex items-center gap-2 text-slate-500 hover:text-teal-600 transition-colors"
          >
            <Download size={18} /> Download Video File
          </a>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-6">
          <div className="relative rounded-xl overflow-hidden shadow-2xl border border-slate-200 bg-slate-50 w-full max-w-4xl h-[600px]">
            <iframe
              src={`${API_BASE}/outputs/${generationResult?.data?.file_url.split('/').pop()}#toolbar=0`}
              className="w-full h-full"
              title="PDF Preview"
            />
          </div>
          <a
            href={`${API_BASE}/download/${generationResult?.data?.file_url.split('/').pop()}`}
            download
            target="_blank"
            className="flex items-center gap-2 text-slate-500 hover:text-teal-600 transition-colors"
          >
            <Download size={18} /> Download PDF File
          </a>
        </div>
      )}

      <div className="mt-12 border-t pt-6">
        <button onClick={() => setPhase('dashboard')} className="text-slate-500 hover:text-teal-600 text-sm font-medium">
          Generate Something Else
        </button>
      </div>
    </motion.div>
  </div>
)

const FolderAccordion = ({ folder, isOpen, onToggle, onSelectFile }) => (
  <div className="rounded-xl overflow-hidden border border-slate-200 bg-white mb-3">
    <div
      onClick={onToggle}
      className={`p-4 flex items-center justify-between cursor-pointer transition-colors ${isOpen ? 'bg-teal-50/50' : 'hover:bg-slate-50'}`}
    >
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 bg-teal-100 text-teal-600 rounded-lg flex items-center justify-center">
          <BookOpen size={16} />
        </div>
        <span className="font-semibold text-slate-700 capitalize">{folder.folder}</span>
      </div>
      <ChevronRight size={18} className={`text-slate-400 transition-transform ${isOpen ? 'rotate-90' : ''}`} />
    </div>
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ height: 0 }}
          animate={{ height: 'auto' }}
          exit={{ height: 0 }}
          className="overflow-hidden bg-slate-50/30"
        >
          <div className="p-2 space-y-1">
            {folder.files.map((file, i) => (
              <div
                key={i}
                onClick={() => onSelectFile(file)}
                className="flex items-center gap-3 p-3 rounded-lg hover:bg-white cursor-pointer group"
              >
                <FileText size={16} className="text-slate-400 group-hover:text-teal-500" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-slate-600 truncate group-hover:text-teal-700">{file.display_name}</div>
                  <div className="text-xs text-slate-400">{file.topics.length} topics</div>
                </div>
                <ChevronRight size={14} className="text-slate-300 opacity-0 group-hover:opacity-100" />
              </div>
            ))}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  </div>
)

// --- MAIN APP ---

function App() {
  const [phase, setPhase] = useState('landing')
  const [isLanding, setIsLanding] = useState(true)
  const [folders, setFolders] = useState([]) // Changed from files to folders
  const [openFolders, setOpenFolders] = useState({})

  const [selectedFile, setSelectedFile] = useState(() => {
    const saved = localStorage.getItem('context_core_selected_file')
    try {
      return saved ? JSON.parse(saved) : null
    } catch (e) {
      return null
    }
  })
  const [selectedTopicIndex, setSelectedTopicIndex] = useState(() => {
    const saved = localStorage.getItem('context_core_topic_idx')
    return saved ? parseInt(saved) : 0
  })
  const [selectedType, setSelectedType] = useState(() => localStorage.getItem('context_core_selected_type') || null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [generationResult, setGenerationResult] = useState(() => {
    const saved = localStorage.getItem('context_core_gen_result')
    try {
      return saved ? JSON.parse(saved) : null
    } catch (e) {
      return null
    }
  })
  const [processingText, setProcessingText] = useState(null)

  // Chat State
  const [isChatOpen, setIsChatOpen] = useState(false)
  const [chatMessages, setChatMessages] = useState([
    { role: 'assistant', content: 'Hello! I am your MathBuddy. Ask me anything about the uploaded curriculum!' }
  ])
  const [currentMessage, setCurrentMessage] = useState('')
  const [isChatLoading, setIsChatLoading] = useState(false)
  const [isListening, setIsListening] = useState(false)

  // Status check
  const [systemOnline, setSystemOnline] = useState(false)

  useEffect(() => {
    // Initial check
    checkSystem()

    // Poll backend status every 10 seconds
    const statusInterval = setInterval(checkSystem, 10000)

    return () => clearInterval(statusInterval)
  }, [])

  // Auto-fetch files when system comes online
  useEffect(() => {
    if (systemOnline) {
      fetchFiles()
    }
  }, [systemOnline])


  // State Persistence: Save to LocalStorage
  useEffect(() => {
    localStorage.setItem('context_core_phase', phase)
    localStorage.setItem('context_core_is_landing', isLanding.toString())
    if (selectedFile) localStorage.setItem('context_core_selected_file', JSON.stringify(selectedFile))
    localStorage.setItem('context_core_topic_idx', selectedTopicIndex.toString())
    if (selectedType) localStorage.setItem('context_core_selected_type', selectedType)
    if (generationResult) localStorage.setItem('context_core_gen_result', JSON.stringify(generationResult))

    // Clear results if going back to landing
    if (phase === 'landing') {
      localStorage.removeItem('context_core_selected_file')
      localStorage.removeItem('context_core_selected_type')
      localStorage.removeItem('context_core_gen_result')
    }
  }, [phase, isLanding, selectedFile, selectedTopicIndex, selectedType, generationResult])

  const checkSystem = async () => {
    try {
      await axios.get(`${API_BASE}/`)
      setSystemOnline(true)
    } catch (e) {
      setSystemOnline(false)
    }
  }

  const fetchFiles = async () => {
    try {
      const res = await axios.get(`${API_BASE}/files`)
      // Expecting [{ folder: "class7", files: [...] }, ...]
      setFolders(res.data)
    } catch (e) {
      console.error("Failed to fetch files")
    }
  }

  const toggleFolder = (folderName) => {
    setOpenFolders(prev => ({
      ...prev,
      [folderName]: !prev[folderName]
    }))
  }

  const handleUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setIsProcessing(true)
    const formData = new FormData()
    formData.append('file', file)
    try {
      await axios.post(`${API_BASE}/upload`, formData)
      await fetchFiles()
      // Stay on landing page as requested
      alert("Upload processed! You can now find your file in the curriculum folders below.")
    } catch (err) {
      alert("Upload failed: " + err.message)
    } finally {
      setIsProcessing(false)
    }
  }

  // Poll for file existence with robust checks
  const pollForFile = async (filename, type) => {
    // Initial delay to allow backend to initialize task
    await new Promise(r => setTimeout(r, 2000));

    let attempts = 0;
    const maxAttempts = 200; // 200 * 3s = 10 minutes timeout

    const interval = setInterval(async () => {
      attempts++;
      if (attempts > maxAttempts) {
        clearInterval(interval);
        alert("Generation timed out or failed in the background. The AI might be rate-limited. Please check server logs.");
        setPhase('dashboard');
        return;
      }
      try {
        const res = await axios.get(`${API_BASE}/download/${filename}`)
        // Ensure file exists AND has content (not empty placeholder)
        const size = res.headers['content-length'];

        if (res.status === 200 && size && parseInt(size) > 1000) {
          clearInterval(interval)
          // Success!
          setGenerationResult({ type: type, data: { file_url: `/download/${filename}`, filename: filename } })
          setPhase('results')
          setProcessingText(null)
        }
      } catch (e) {
        // Continue polling if 404
        console.log("Polling for video...", filename, `(Attempt ${attempts}/${maxAttempts})`)
      }
    }, 3000) // Check every 3 seconds
  }

  const handleGenerate = async (overrideType = null) => {
    const targetType = overrideType || selectedType
    if (!selectedFile || !targetType) return
    setPhase('generating')
    setProcessingText(null)

    try {
      let endpoint = ''
      switch (targetType) {
        case 'plan': endpoint = '/generate/plan'; break;
        case 'quiz': endpoint = '/generate/quiz'; break;
        case 'practice': endpoint = '/generate/practice'; break;
        case 'flashcards': endpoint = '/generate/flashcards'; break;
        case 'video': endpoint = '/generate/video'; break;
        case 'resources': endpoint = '/generate/resources'; break;
        case 'youtube': endpoint = '/generate/youtube'; break;
        default: throw new Error("Unknown type");
      }
      const payload = {
        filename: selectedFile.filename, // This contains relative path now
        topic_index: selectedTopicIndex
      }

      if (targetType === 'video') {
        setProcessingText("Generating your video... This may take up to 2-3 minutes. Please stay on this screen.")
      }

      console.log("Sending request to:", endpoint, payload)
      const res = await axios.post(`${API_BASE}${endpoint}`, payload)
      console.log("Response:", res.data)

      if (!res.data) {
        throw new Error("Empty response from server")
      }

      // STRICT CHECK: For video, we MUST go into polling mode.
      if (targetType === 'video' || res.data.status === 'processing') {
        const fileToPoll = res.data.filename || res.data.json_file

        if (!fileToPoll) {
          throw new Error("No filename returned for background task")
        }

        console.log("Starting polling for (UNIQUE):", fileToPoll)
        pollForFile(fileToPoll, targetType)
        return; // Explicit return to prevent fallthrough
      }

      // Immediate result types (for non-video)
      setGenerationResult({ type: targetType, data: res.data })
      setPhase('results')

    } catch (err) {
      console.error("Generation Error:", err)
      alert("Generation failed: " + (err.response?.data?.detail || err.message))
      setPhase('dashboard')
    }
  }

  const handleSendMessage = async () => {
    if (!currentMessage.trim()) return
    const userMsg = { role: 'user', content: currentMessage }
    setChatMessages(prev => [...prev, userMsg])
    setCurrentMessage('')
    setIsChatLoading(true)
    try {
      const res = await axios.post(`${API_BASE}/chat`, { message: userMsg.content })
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: res.data.answer,
        sources: res.data.sources || []
      }])
    } catch (e) {
      setChatMessages(prev => [...prev, { role: 'assistant', content: "Error: Could not connect to Chatbot." }])
    } finally {
      setIsChatLoading(false)
    }
  }

  // Voice Input Logic
  const handleMicClick = () => {
    if (!('webkitSpeechRecognition' in window)) {
      alert("Voice input is not supported in this browser. Try Chrome/Edge.")
      return
    }

    if (isListening) {
      window.speechRecognitionInstance?.stop()
      setIsListening(false)
      return
    }

    const recognition = new window.webkitSpeechRecognition()
    recognition.continuous = false
    recognition.interimResults = false
    recognition.lang = 'en-US'

    recognition.onstart = () => {
      setIsListening(true)
    }

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript
      setCurrentMessage(prev => prev + (prev ? ' ' : '') + transcript)
      setIsListening(false)
    }

    recognition.onerror = (event) => {
      console.error("Speech Recognition Error", event.error)
      setIsListening(false)
    }

    recognition.onend = () => {
      setIsListening(false)
    }

    window.speechRecognitionInstance = recognition
    recognition.start()
  }

  // Text to Speech
  const handleSpeak = (text) => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel() // Stop any current speech
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.rate = 1.1 // Slightly faster
      window.speechSynthesis.speak(utterance)
    }
  }

  if (isLanding) {
    return <LandingPage onGetStarted={() => {
      setIsLanding(false)
      setPhase('landing')
    }} />;
  }

  return (
    <div className="min-h-screen bg-soft">
      <Header systemOnline={systemOnline} onHome={() => setIsLanding(true)} />

      <AnimatePresence mode='wait'>
        {phase === 'landing' && (
          <div className="pt-24 min-h-screen flex items-center justify-center p-6">
            <div className="app-grid w-full">
              {/* Upload Card */}
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="glass-panel p-8 flex flex-col items-center justify-center text-center min-h-[400px]">
                <div className={`relative w-full h-full border-2 border-dashed border-slate-300 rounded-xl flex flex-col items-center justify-center p-6 transition-all ${isProcessing ? 'bg-slate-50' : 'hover:border-teal-400 hover:bg-slate-50'}`}>
                  {isProcessing ? (
                    <div className="flex flex-col items-center">
                      <div className="loader-spinner mb-4"></div>
                      <h3 className="text-lg font-semibold text-slate-700">Processing Document...</h3>
                      <p className="text-sm text-slate-500">Extracting curriculum hierarchy</p>
                    </div>
                  ) : (
                    <>
                      <div className="w-16 h-16 bg-teal-50 text-teal-500 rounded-full flex items-center justify-center mb-4">
                        <Upload size={32} />
                      </div>
                      <h3 className="text-xl font-semibold mb-2 text-slate-700">Upload Curriculum PDF</h3>
                      <p className="text-slate-500 mb-6 max-w-xs">Drag and drop your NCERT chapter or textbook directory here.</p>
                      <input type="file" onChange={handleUpload} className="hidden" id="file-upload" />
                      <label htmlFor="file-upload" className="btn-primary">
                        Choose File
                      </label>
                    </>
                  )}
                </div>
              </motion.div>

              {/* Recent Files (Folders now) */}
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="flex flex-col gap-4">
                <h2 className="text-xl font-bold text-slate-700">Curriculum Content</h2>
                <div className="grid gap-2">
                  {folders.length === 0 ? (
                    <div className="glass-panel p-6 text-center text-slate-400">No content found in /content folder.</div>
                  ) : (
                    folders.map((folder, i) => (
                      <FolderAccordion
                        key={i}
                        folder={folder}
                        isOpen={openFolders[folder.folder]}
                        onToggle={() => toggleFolder(folder.folder)}
                        onSelectFile={(f) => { setSelectedFile(f); setPhase('dashboard'); }}
                      />
                    ))
                  )}
                </div>
              </motion.div>
            </div>
          </div>
        )}
        {phase === 'dashboard' && (
          <DashboardView
            key="dashboard"
            setPhase={setPhase}
            selectedFile={selectedFile}
            selectedTopicIndex={selectedTopicIndex}
            setSelectedTopicIndex={setSelectedTopicIndex}
            selectedType={selectedType}
            setSelectedType={setSelectedType}
            handleGenerate={handleGenerate}
          />
        )}
        {phase === 'dashboard-analytics' && (
          <Dashboard onBack={() => setPhase('dashboard')} />
        )}
        {phase === 'generating' && <GeneratingView key="loading" processingText={processingText} />}
        {phase === 'results' && (
          <ResultsView
            key="results"
            selectedType={selectedType}
            selectedFile={selectedFile}
            selectedTopicIndex={selectedTopicIndex}
            generationResult={generationResult}
            setPhase={setPhase}
          />
        )}
      </AnimatePresence>

      {/* Chat Widget */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-4">
        {/* ... Chat Widget Code Same ... */}
        <AnimatePresence>
          {isChatOpen && (
            <motion.div initial={{ opacity: 0, scale: 0.9, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.9, y: 20 }} className="glass-panel w-80 h-[500px] flex flex-col shadow-2xl bg-white border border-slate-200">
              <div className="p-4 border-b flex justify-between items-center bg-teal-50 rounded-t-xl">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                  <h4 className="font-bold text-slate-700">MathBuddy AI</h4>
                </div>
                <button onClick={() => setIsChatOpen(false)} className="text-slate-400 hover:text-red-500"><X size={18} /></button>
              </div>
              <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
                {chatMessages.map((msg, idx) => (
                  <div key={idx} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                    <div className={`max-w-[85%] p-3 rounded-lg text-sm ${msg.role === 'user' ? 'bg-teal-500 text-white rounded-br-none' : 'bg-slate-100 text-slate-700 rounded-bl-none'}`}>
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>

                    {/* TTS Button for Assistant */}
                    {msg.role === 'assistant' && (
                      <button
                        onClick={() => handleSpeak(msg.content)}
                        className="mt-1 ml-1 text-slate-400 hover:text-teal-600 self-start p-1"
                        title="Read Aloud"
                      >
                        <Volume2 size={14} />
                      </button>
                    )}

                    {/* Display Sources */}
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-2 text-[10px] text-slate-400 max-w-[85%] bg-slate-50 p-2 rounded border border-slate-100">
                        <div className="font-bold mb-1"> Sources:</div>
                        {msg.sources.map((s, i) => (
                          <div key={i} className="truncate"> {s.topic}</div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                {isChatLoading && <div className="text-xs text-slate-400 pl-2">MathBuddy is thinking...</div>}
              </div>
              <div className="p-3 border-t flex gap-2">
                <input
                  value={currentMessage}
                  onChange={(e) => setCurrentMessage(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                  placeholder="Ask a doubt..."
                  className="flex-1 bg-slate-50 border border-slate-200 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-teal-400"
                />
                <button
                  onClick={handleMicClick}
                  className={`p-2 rounded-md transition-colors ${isListening ? 'bg-red-500 text-white animate-pulse' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'}`}
                  title="Voice Input"
                >
                  {isListening ? <MicOff size={16} /> : <Mic size={16} />}
                </button>
                <button onClick={handleSendMessage} disabled={isChatLoading} className="bg-teal-500 text-white p-2 rounded-md hover:bg-teal-600 disabled:opacity-50">
                  <Send size={16} />
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <button
          onClick={() => setIsChatOpen(!isChatOpen)}
          className="w-14 h-14 bg-gradient-to-tr from-teal-500 to-blue-500 rounded-full shadow-lg flex items-center justify-center text-white hover:scale-110 transition-transform"
        >
          {isChatOpen ? <X size={24} /> : <MessageSquare size={24} />}
        </button>
      </div>
    </div>
  )
}

export default App
