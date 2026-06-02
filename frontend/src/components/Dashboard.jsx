import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer,
    BarChart, Bar, XAxis, YAxis, Tooltip, Cell
} from 'recharts';
import {
    Brain, Activity, TrendingUp, AlertTriangle, BookOpen, ChevronRight, Award,
    CheckCircle, Clock, Zap, Target, Map, RefreshCw, AlertCircle, Star, ArrowRight
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE;

const getAuthHeaders = () => {
    const token = localStorage.getItem('context_core_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
};

// ─── Level Badge ────────────────────────────────────────────────────────────
const LevelBadge = ({ level }) => {
    const colors = {
        Beginner: 'bg-emerald-100 text-emerald-700 border-emerald-200',
        Intermediate: 'bg-amber-100 text-amber-700 border-amber-200',
        Advanced: 'bg-purple-100 text-purple-700 border-purple-200'
    };
    return (
        <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${colors[level] || 'bg-slate-100 text-slate-600 border-slate-200'}`}>
            {level}
        </span>
    );
};

// ─── Mastery Bar ─────────────────────────────────────────────────────────────
const MasteryBar = ({ value, color = 'bg-violet-500', label }) => (
    <div className="flex items-center gap-2">
        {label && <span className="text-[10px] text-slate-400 w-16 shrink-0">{label}</span>}
        <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
            <motion.div
                className={`h-full rounded-full ${color}`}
                initial={{ width: 0 }}
                animate={{ width: `${Math.round(value)}%` }}
                transition={{ duration: 0.8, ease: 'easeOut' }}
            />
        </div>
        <span className="text-xs font-semibold text-slate-600 w-8 text-right">{Math.round(value)}%</span>
    </div>
);

// ─── Event Icon ───────────────────────────────────────────────────────────────
const eventConfig = {
    quiz_submit:     { icon: <CheckCircle size={14} />, color: 'text-teal-500',  bg: 'bg-teal-50',   label: 'Quiz' },
    mastery_update:  { icon: <Brain size={14} />,       color: 'text-violet-500', bg: 'bg-violet-50', label: 'Mastery' },
    prereq_warning:  { icon: <AlertTriangle size={14}/>, color: 'text-amber-500', bg: 'bg-amber-50',  label: 'Prereq Gap' },
    level_promotion: { icon: <Star size={14} />,         color: 'text-yellow-500', bg: 'bg-yellow-50', label: 'Promoted!' },
    spaced_repetition: { icon: <RefreshCw size={14} />, color: 'text-blue-500',  bg: 'bg-blue-50',   label: 'Revision' },
};

// ─── Timeline Event ───────────────────────────────────────────────────────────
const TimelineEvent = ({ event, idx }) => {
    const cfg = eventConfig[event.event_type] || { icon: <Activity size={14} />, color: 'text-slate-400', bg: 'bg-slate-50', label: 'Event' };
    const timeStr = new Date(event.timestamp).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    return (
        <motion.div
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: idx * 0.04 }}
            className="flex gap-3 items-start"
        >
            <div className="flex flex-col items-center">
                <div className={`w-7 h-7 rounded-full ${cfg.bg} ${cfg.color} flex items-center justify-center shrink-0 border border-white shadow-sm`}>
                    {cfg.icon}
                </div>
                <div className="w-px flex-1 bg-slate-100 mt-1 min-h-[16px]" />
            </div>
            <div className="pb-4 flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                    <span className={`text-[10px] font-bold uppercase tracking-wider ${cfg.color}`}>{cfg.label}</span>
                    {event.topic && <span className="text-[10px] text-slate-400 truncate">· {event.topic}</span>}
                    <span className="ml-auto text-[10px] text-slate-300 shrink-0">{timeStr}</span>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">{event.description}</p>
            </div>
        </motion.div>
    );
};

// ─── Custom Radar Tooltip ───────────────────────────────────────────────────
const CustomRadarTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
        const item = payload[0].payload;
        return (
            <div className="bg-slate-950/95 backdrop-blur-md text-white border border-slate-800 shadow-2xl rounded-2xl p-4 text-xs font-semibold leading-relaxed max-w-[240px] pointer-events-none">
                <p className="font-extrabold text-violet-300 text-sm mb-2 truncate">{item.subject}</p>
                <div className="space-y-1.5 font-medium">
                    <div className="flex justify-between gap-4">
                        <span className="text-slate-300">Quiz Average:</span>
                        <span className="font-extrabold text-slate-100">{item.A}%</span>
                    </div>
                    <div className="flex justify-between gap-4">
                        <span className="text-slate-300">Mastery:</span>
                        <span className="font-extrabold text-violet-400">{item.mastery !== undefined ? `${item.mastery}%` : '0%'}</span>
                    </div>
                    <div className="flex justify-between gap-4">
                        <span className="text-slate-300">Confidence:</span>
                        <span className="font-extrabold text-teal-400">{item.confidence !== undefined ? `${item.confidence}%` : '0%'}</span>
                    </div>
                    <div className="flex justify-between gap-4">
                        <span className="text-slate-300">Retention:</span>
                        <span className="font-extrabold text-emerald-400">{item.retention !== undefined ? `${item.retention}%` : '0%'}</span>
                    </div>
                </div>
            </div>
        );
    }
    return null;
};

// ─── Main Dashboard ───────────────────────────────────────────────────────────
const Dashboard = ({ onBack }) => {
    const [loading, setLoading] = useState(true);
    const [data, setData]       = useState(null);
    const [profile, setProfile] = useState(null);
    const [mastery, setMastery] = useState([]);
    const [timeline, setTimeline] = useState({ timeline: [], velocity: {}, revision_schedule: [] });
    const [roadmap, setRoadmap] = useState([]);
    const [activeTab, setActiveTab] = useState('overview');

    useEffect(() => { fetchAll(); }, []);

    const fetchAll = async () => {
        try {
            const headers = getAuthHeaders();
            const [analyticsRes, profileRes, masteryRes, timelineRes, roadmapRes] = await Promise.all([
                axios.get(`${API_BASE}/dashboard/analytics`, { headers }),
                axios.get(`${API_BASE}/learner/profile`, { headers }),
                axios.get(`${API_BASE}/learner/mastery`, { headers }).catch(() => ({ data: { mastery: [] } })),
                axios.get(`${API_BASE}/learner/timeline`, { headers }).catch(() => ({ data: { timeline: [], velocity: {}, revision_schedule: [] } })),
                axios.get(`${API_BASE}/learner/roadmap`, { headers }).catch(() => ({ data: { roadmap: [] } })),
            ]);
            setData(analyticsRes.data);
            setProfile(profileRes.data);
            setMastery(masteryRes.data.mastery || []);
            setTimeline(timelineRes.data || { timeline: [], velocity: {}, revision_schedule: [] });
            setRoadmap(roadmapRes.data.roadmap || []);
        } catch (err) {
            console.error('Dashboard fetch error', err);
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="min-h-[600px] flex flex-col items-center justify-center gap-4">
                <div className="w-12 h-12 rounded-full border-4 border-violet-200 border-t-violet-600 animate-spin" />
                <p className="text-slate-400 text-sm">Loading learner intelligence…</p>
            </div>
        );
    }

    const userName = localStorage.getItem('context_core_user_name') || 'Learner';
    const velocity = timeline.velocity || {};
    const revisionItems = timeline.revision_schedule || [];
    const timelineEvents = timeline.timeline || [];

    const velocityColor = {
        'Rapidly Rising': 'text-emerald-600',
        'Steady Growth': 'text-teal-600',
        'Maintaining Score Levels': 'text-slate-500',
        'Struggling Pattern Detected': 'text-red-500',
    }[velocity.velocity_status] || 'text-slate-500';

    const tabs = [
        { id: 'overview', label: 'Overview', icon: <Brain size={14} /> },
        { id: 'mastery', label: 'Topic Mastery', icon: <Target size={14} /> },
        { id: 'timeline', label: 'Timeline', icon: <Clock size={14} /> },
        { id: 'roadmap', label: 'Roadmap', icon: <Map size={14} /> },
    ];

    return (
        <div className="pt-24 px-4 md:px-8 max-w-7xl mx-auto pb-24">

            {/* ── Header ── */}
            <div className="mb-8 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-extrabold text-slate-800 tracking-tight">Learning Intelligence</h1>
                    <p className="text-slate-500 mt-1">
                        Welcome back, <span className="font-semibold text-violet-600">{userName}</span>
                        {velocity.velocity_status && (
                            <span className={`ml-2 text-sm font-medium ${velocityColor}`}>
                                · {velocity.velocity_status}
                            </span>
                        )}
                    </p>
                </div>
                <button onClick={onBack} className="text-sm font-semibold text-slate-400 hover:text-violet-600 transition-colors flex items-center gap-1">
                    <ChevronRight size={14} className="rotate-180" /> Back to Generator
                </button>
            </div>

            {/* ── Summary Cards ── */}
            {profile && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                    {[
                        { label: 'Global Rank', value: `${profile.current_level} Tier`, icon: '🎓', color: 'violet' },
                        { label: 'Topics Mastered', value: `${mastery.filter(m => m.mastery_score >= 0.75).length}`, icon: '💎', color: 'emerald' },
                        { label: 'Revision Due', value: `${revisionItems.length}`, icon: '🔁', color: 'amber' },
                        { label: 'Concepts Tracked', value: `${mastery.length}`, icon: '📊', color: 'blue' },
                    ].map(({ label, value, icon, color }) => (
                        <motion.div
                            key={label}
                            initial={{ opacity: 0, y: 8 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="bg-white rounded-2xl border border-slate-100 shadow-sm p-4 flex items-center justify-between"
                        >
                            <div>
                                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{label}</p>
                                <p className={`text-xl font-extrabold text-${color}-600 mt-1`}>{value}</p>
                            </div>
                            <div className={`w-11 h-11 rounded-xl bg-${color}-50 flex items-center justify-center text-xl`}>{icon}</div>
                        </motion.div>
                    ))}
                </div>
            )}

            {/* ── Tabs ── */}
            <div className="flex gap-1 bg-slate-100 rounded-xl p-1 mb-8 w-fit">
                {tabs.map(t => (
                    <button
                        key={t.id}
                        onClick={() => setActiveTab(t.id)}
                        className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
                            activeTab === t.id
                                ? 'bg-white text-violet-700 shadow-sm'
                                : 'text-slate-500 hover:text-slate-700'
                        }`}
                    >
                        {t.icon}{t.label}
                    </button>
                ))}
            </div>

            <AnimatePresence mode="wait">

                {/* ════════════════════ OVERVIEW ════════════════════ */}
                {activeTab === 'overview' && (
                    <motion.div key="overview" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                            {/* Radar Chart */}
                            <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-6 flex flex-col">
                                <div className="flex items-center gap-2 mb-4">
                                    <div className="w-9 h-9 bg-violet-100 text-violet-600 rounded-xl flex items-center justify-center"><Brain size={18} /></div>
                                    <h3 className="font-bold text-slate-700">Topic Proficiency</h3>
                                </div>
                                {data?.spider_data?.length > 0 ? (
                                    <div className="flex-1 min-h-[260px] -ml-4">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data.spider_data}>
                                                <PolarGrid stroke="#cbd5e1" />
                                                <PolarAngleAxis dataKey="subject" tick={{ fill: '#475569', fontSize: 9, fontWeight: 600 }} />
                                                <PolarRadiusAxis angle={30} domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tick={{ fill: '#94a3b8', fontSize: 8, fontWeight: 500 }} axisLine={false} />
                                                <Radar name="Quiz Average" dataKey="A" stroke="#7c3aed" strokeWidth={2} fill="#7c3aed" fillOpacity={0.15} />
                                                <Tooltip content={<CustomRadarTooltip />} />
                                            </RadarChart>
                                        </ResponsiveContainer>
                                    </div>
                                ) : (
                                    <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">Take quizzes to generate your proficiency map</div>
                                )}
                            </div>

                            {/* Right column */}
                            <div className="lg:col-span-2 space-y-5">

                                {/* Velocity Banner */}
                                <div className="bg-gradient-to-r from-violet-600 to-indigo-600 rounded-2xl p-5 text-white flex items-center justify-between">
                                    <div>
                                        <p className="text-violet-200 text-xs font-semibold uppercase tracking-wider mb-1">Learning Velocity</p>
                                        <p className="text-2xl font-extrabold">{velocity.velocity_status || 'Needs More Data'}</p>
                                        <p className="text-violet-200 text-sm mt-1">
                                            {velocity.absorption_speed && `Absorption: ${velocity.absorption_speed}`}
                                            {velocity.overall_improvement !== undefined && ` · ${velocity.overall_improvement > 0 ? '+' : ''}${velocity.overall_improvement}% overall`}
                                        </p>
                                    </div>
                                    <div className="w-14 h-14 rounded-2xl bg-white/20 flex items-center justify-center">
                                        <Zap size={28} className="text-white" />
                                    </div>
                                </div>

                                {/* Prerequisite Gaps (if any) */}
                                {data?.weakest_topics?.length > 0 && (
                                    <div className="bg-red-50 border border-red-100 rounded-2xl p-5">
                                        <div className="flex gap-3 items-start">
                                            <AlertTriangle size={20} className="text-red-500 shrink-0 mt-0.5" />
                                            <div>
                                                <h4 className="font-bold text-red-800 mb-1">Attention Needed</h4>
                                                <p className="text-red-600 text-sm">
                                                    Struggling with <b>{data.weakest_topics[0].topic}</b> ({data.weakest_topics[0].score}% avg).
                                                    {' '}Switch to Beginner mode and review foundational examples first.
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* Today's Revision Queue */}
                                {revisionItems.length > 0 && (
                                    <div className="bg-white border border-slate-100 rounded-2xl shadow-sm p-5">
                                        <div className="flex items-center gap-2 mb-4">
                                            <div className="w-9 h-9 bg-amber-100 text-amber-600 rounded-xl flex items-center justify-center"><RefreshCw size={16} /></div>
                                            <h3 className="font-bold text-slate-700">Today's Revision Queue</h3>
                                            <span className="ml-auto text-xs text-slate-400">{revisionItems.length} topics need review</span>
                                        </div>
                                        <div className="space-y-4">
                                            {revisionItems.map((item, i) => {
                                                const priorityColors = {
                                                    high: "bg-red-50 text-red-700 border-red-100",
                                                    medium: "bg-amber-50 text-amber-700 border-amber-100",
                                                    low: "bg-blue-50 text-blue-700 border-blue-100",
                                                }[item.urgency] || "bg-slate-50 text-slate-700 border-slate-100";
                                                
                                                return (
                                                    <div key={i} className="bg-slate-50/50 rounded-xl p-4 border border-slate-100/80 transition-all hover:bg-slate-50 hover:shadow-sm">
                                                        <div className="flex items-start justify-between gap-3 mb-2.5">
                                                            <div>
                                                                <h4 className="text-sm font-bold text-slate-800">{item.topic}</h4>
                                                                <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border mt-1 inline-block ${priorityColors}`}>
                                                                    {item.urgency || 'medium'} Priority
                                                                </span>
                                                            </div>
                                                            <div className="text-right shrink-0">
                                                                <span className="text-[10px] text-slate-400 uppercase font-bold block">Composite Score</span>
                                                                <span className="text-sm font-extrabold text-slate-700">{item.priority_score || '0.5'}</span>
                                                            </div>
                                                        </div>

                                                        {/* Explainable Reasons */}
                                                        <div className="mt-2.5 space-y-1.5">
                                                            <span className="text-[10px] text-slate-400 uppercase font-bold block">Why revision is due:</span>
                                                            <ul className="list-disc list-inside text-xs text-slate-600 space-y-1 font-medium">
                                                                {item.mastery_percentage < 60 && (
                                                                    <li>Low Mastery detected ({item.mastery_percentage}%)</li>
                                                                )}
                                                                {item.retention_percentage < 50 && (
                                                                    <li>Retention Below Threshold ({item.retention_percentage}%)</li>
                                                                )}
                                                                {item.confidence_percentage < 50 && (
                                                                    <li>Low Confidence building needed ({item.confidence_percentage}%)</li>
                                                                )}
                                                                {item.last_studied_days >= 7 && (
                                                                    <li>Inactive for {item.last_studied_days} days</li>
                                                                )}
                                                                {item.mastery_percentage < 40 && (
                                                                    <li>Prerequisite Requirement warning</li>
                                                                )}
                                                            </ul>
                                                            <div className="mt-2 text-xs italic text-slate-500 bg-white border border-slate-100 p-2 rounded-lg">
                                                                {item.reason}
                                                            </div>
                                                        </div>

                                                        {/* Metrics Grid */}
                                                        <div className="grid grid-cols-3 gap-2 mt-3 bg-white p-2.5 rounded-lg border border-slate-100 text-[10px] text-center font-bold">
                                                            <div>
                                                                <span className="text-slate-400 uppercase block font-semibold">Mastery</span>
                                                                <span className="text-violet-600 text-xs font-extrabold">{item.mastery_percentage}%</span>
                                                            </div>
                                                            <div>
                                                                <span className="text-slate-400 uppercase block font-semibold">Confidence</span>
                                                                <span className="text-teal-600 text-xs font-extrabold">{item.confidence_percentage}%</span>
                                                            </div>
                                                            <div>
                                                                <span className="text-slate-400 uppercase block font-semibold">Retention</span>
                                                                <span className="text-emerald-600 text-xs font-extrabold">{item.retention_percentage}%</span>
                                                            </div>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                )}

                                {/* AI Focus Recommendations with Explainability */}
                                {data?.recommendations?.length > 0 && (
                                    <div className="bg-white border border-slate-100 rounded-2xl shadow-sm p-5">
                                        <div className="flex items-center gap-2 mb-4">
                                            <div className="w-9 h-9 bg-teal-100 text-teal-600 rounded-xl flex items-center justify-center"><TrendingUp size={16} /></div>
                                            <h3 className="font-bold text-slate-700">AI Focus Recommendations</h3>
                                        </div>
                                        <div className="space-y-4">
                                            {data.recommendations.map((rec, idx) => (
                                                <div key={idx} className="bg-slate-50 rounded-xl p-4 border border-slate-100/80 transition-all hover:shadow-sm">
                                                    <p className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">Improve · {rec.topic}</p>
                                                    <p className="text-sm text-slate-700 font-medium">{rec.suggestion}</p>
                                                    
                                                    {/* "Why am I seeing this?" Collapsible Section */}
                                                    <details className="group mt-3 bg-white border border-slate-100 rounded-xl p-3 cursor-pointer select-none overflow-hidden transition-all duration-300">
                                                        <summary className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center justify-between hover:text-violet-600">
                                                            <span>Why am I seeing this?</span>
                                                            <ChevronRight size={14} className="transform group-open:rotate-90 transition-transform duration-200" />
                                                        </summary>
                                                        <div className="mt-3 space-y-2.5 border-t border-slate-100 pt-3 text-xs text-slate-600 font-medium">
                                                            <div className="grid grid-cols-2 gap-2">
                                                                <div className="bg-slate-50 border border-slate-100 p-2 rounded-lg">
                                                                    <span className="text-[10px] text-slate-400 block uppercase font-bold">Mastery</span>
                                                                    <span className="font-extrabold text-violet-600 text-sm">{rec.mastery_percentage}%</span>
                                                                </div>
                                                                <div className="bg-slate-50 border border-slate-100 p-2 rounded-lg">
                                                                    <span className="text-[10px] text-slate-400 block uppercase font-bold">Confidence</span>
                                                                    <span className="font-extrabold text-teal-600 text-sm">{rec.confidence_percentage}%</span>
                                                                </div>
                                                                <div className="bg-slate-50 border border-slate-100 p-2 rounded-lg">
                                                                    <span className="text-[10px] text-slate-400 block uppercase font-bold">Retention</span>
                                                                    <span className="font-extrabold text-emerald-600 text-sm">{rec.retention_percentage}%</span>
                                                                </div>
                                                                <div className="bg-slate-50 border border-slate-100 p-2 rounded-lg">
                                                                    <span className="text-[10px] text-slate-400 block uppercase font-bold">Suggested Level</span>
                                                                    <span className="font-extrabold text-slate-700 text-sm">{rec.difficulty_recommendation || 'Beginner'}</span>
                                                                </div>
                                                            </div>
                                                            
                                                            <div className="bg-slate-50 border border-slate-100 p-2.5 rounded-lg flex justify-between items-center">
                                                                <span className="text-[10px] text-slate-400 uppercase font-bold">Prerequisite Weight</span>
                                                                <span className="font-extrabold text-indigo-600 text-xs px-2.5 py-0.5 rounded-full bg-indigo-50 border border-indigo-100">
                                                                    {rec.prereq_weight || 'Medium'}
                                                                </span>
                                                            </div>

                                                            <div className="bg-slate-50 border border-slate-100 p-3 rounded-lg space-y-2">
                                                                <span className="text-[10px] text-slate-400 block uppercase font-bold">Triggered By:</span>
                                                                <div className="space-y-1.5 text-slate-600 font-semibold">
                                                                    <div className="flex items-center gap-1.5">
                                                                        <span className={rec.mastery_percentage < 50 ? "text-emerald-600 font-bold" : "text-slate-300 font-bold"}>
                                                                            {rec.mastery_percentage < 50 ? "✓" : "✗"}
                                                                        </span>
                                                                        <span className={rec.mastery_percentage < 50 ? "text-slate-700" : "text-slate-400 line-through font-normal"}>Low Mastery</span>
                                                                    </div>
                                                                    <div className="flex items-center gap-1.5">
                                                                        <span className={rec.retention_percentage < 50 ? "text-emerald-600 font-bold" : "text-slate-300 font-bold"}>
                                                                            {rec.retention_percentage < 50 ? "✓" : "✗"}
                                                                        </span>
                                                                        <span className={rec.retention_percentage < 50 ? "text-slate-700" : "text-slate-400 line-through font-normal"}>Retention Decay</span>
                                                                    </div>
                                                                    <div className="flex items-center gap-1.5">
                                                                        <span className={rec.prereq_weight === 'High' ? "text-emerald-600 font-bold" : "text-slate-300 font-bold"}>
                                                                            {rec.prereq_weight === 'High' ? "✓" : "✗"}
                                                                        </span>
                                                                        <span className={rec.prereq_weight === 'High' ? "text-slate-700" : "text-slate-400 line-through font-normal"}>Prerequisite Gap</span>
                                                                    </div>
                                                                </div>
                                                            </div>

                                                            {rec.reason && (
                                                                <div className="bg-violet-50/50 border border-violet-100/50 p-2.5 rounded-lg text-slate-600 leading-relaxed italic">
                                                                    "{rec.reason}"
                                                                </div>
                                                            )}
                                                        </div>
                                                    </details>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </motion.div>
                )}

                {/* ════════════════════ MASTERY ════════════════════ */}
                {activeTab === 'mastery' && (
                    <motion.div key="mastery" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                        {mastery.length === 0 ? (
                            <div className="text-center py-20 text-slate-400">
                                <Target size={48} className="mx-auto mb-4 text-slate-200" />
                                <p>No mastery data yet. Complete some quizzes to track your progress.</p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {mastery.map((m, i) => (
                                    <motion.div
                                        key={m.topic}
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: i * 0.05 }}
                                        className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5"
                                    >
                                        <div className="flex items-start justify-between mb-3">
                                            <div className="flex-1 min-w-0">
                                                <h4 className="font-bold text-slate-800 truncate">{m.topic}</h4>
                                                <p className="text-xs text-slate-400 mt-0.5">{m.attempt_count} attempts · avg {Math.round(m.average_quiz_score)}%</p>
                                            </div>
                                            <LevelBadge level={m.estimated_level} />
                                        </div>

                                        <div className="space-y-2.5">
                                            <MasteryBar value={m.mastery_percentage} color="bg-violet-500" label="Mastery" />
                                            <MasteryBar value={m.confidence_percentage} color="bg-teal-500" label="Confidence" />
                                            <MasteryBar value={m.retention_percentage} color={m.retention_percentage < 50 ? 'bg-red-400' : 'bg-emerald-400'} label="Retention" />
                                        </div>

                                        {/* Confidence Drivers Display */}
                                        {m.confidence_evidence && m.confidence_evidence.evidence && (
                                            <div className="mt-4 pt-3 border-t border-slate-100">
                                                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Confidence Drivers</p>
                                                <div className="grid grid-cols-2 gap-2 text-[10px] text-slate-500">
                                                    <div className="flex justify-between bg-slate-50/50 p-2 rounded border border-slate-100">
                                                        <span className="text-slate-400 font-medium">Response Speed</span>
                                                        <span className="font-extrabold text-teal-600">{Math.round((m.confidence_evidence.evidence.response_speed || 0) * 100)}%</span>
                                                    </div>
                                                    <div className="flex justify-between bg-slate-50/50 p-2 rounded border border-slate-100">
                                                        <span className="text-slate-400 font-medium">Hint Stability</span>
                                                        <span className="font-extrabold text-teal-600">{Math.round((m.confidence_evidence.evidence.hint_usage || 0) * 100)}%</span>
                                                    </div>
                                                    <div className="flex justify-between bg-slate-50/50 p-2 rounded border border-slate-100">
                                                        <span className="text-slate-400 font-medium">Answer Stability</span>
                                                        <span className="font-extrabold text-teal-600">{Math.round((m.confidence_evidence.evidence.answer_stability || 0) * 100)}%</span>
                                                    </div>
                                                    <div className="flex justify-between bg-slate-50/50 p-2 rounded border border-slate-100">
                                                        <span className="text-slate-400 font-medium">Clarification Behavior</span>
                                                        <span className="font-extrabold text-teal-600">{Math.round((m.confidence_evidence.evidence.clarification_behavior || 0) * 100)}%</span>
                                                    </div>
                                                </div>
                                            </div>
                                        )}

                                        {m.retention_percentage < 50 && (
                                            <div className="mt-3 flex items-center gap-1.5 text-amber-600 bg-amber-50 rounded-lg px-3 py-1.5">
                                                <AlertCircle size={12} />
                                                <span className="text-xs font-medium">Memory fading — revision recommended</span>
                                            </div>
                                        )}
                                    </motion.div>
                                ))}
                            </div>
                        )}
                    </motion.div>
                )}

                {/* ════════════════════ TIMELINE ════════════════════ */}
                {activeTab === 'timeline' && (
                    <motion.div key="timeline" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                            <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-100 shadow-sm p-6">
                                <h3 className="font-bold text-slate-700 mb-5">Learning Event Log</h3>
                                {timelineEvents.length === 0 ? (
                                    <p className="text-slate-400 text-sm text-center py-12">No events yet. Complete your first quiz to start tracking.</p>
                                ) : (
                                    <div className="overflow-y-auto max-h-[520px] pr-2">
                                        {timelineEvents.map((ev, i) => (
                                            <TimelineEvent key={i} event={ev} idx={i} />
                                        ))}
                                    </div>
                                )}
                            </div>

                            <div className="space-y-4">
                                {/* Velocity Card */}
                                <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
                                    <h4 className="font-bold text-slate-700 mb-3 flex items-center gap-2"><Zap size={16} className="text-violet-500" />Velocity Stats</h4>
                                    <div className="space-y-2">
                                        {[
                                            ['Status', velocity.velocity_status || '—'],
                                            ['Absorption', velocity.absorption_speed || '—'],
                                            ['Net Improvement', velocity.overall_improvement !== undefined ? `${velocity.overall_improvement > 0 ? '+' : ''}${velocity.overall_improvement}%` : '—'],
                                            ['Attempts', velocity.total_attempts || '—']
                                        ].map(([k, v]) => (
                                            <div key={k} className="flex justify-between text-sm">
                                                <span className="text-slate-400">{k}</span>
                                                <span className="font-semibold text-slate-700">{v}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* Revision Schedule */}
                                {revisionItems.length > 0 && (
                                    <div className="bg-amber-50 rounded-2xl border border-amber-100 p-5">
                                        <h4 className="font-bold text-amber-800 mb-3 flex items-center gap-2"><RefreshCw size={14} />Urgent Revisions</h4>
                                        <div className="space-y-2">
                                            {revisionItems.map((item, i) => (
                                                <div key={i} className="flex items-center justify-between text-sm">
                                                    <span className="text-amber-700 font-medium truncate">{item.topic}</span>
                                                    <span className="text-amber-500 shrink-0 ml-2">{item.retention_percentage}%</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </motion.div>
                )}

                {/* ════════════════════ ROADMAP ════════════════════ */}
                {activeTab === 'roadmap' && (
                    <motion.div key="roadmap" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                        {roadmap.length === 0 ? (
                            <div className="text-center py-20 text-slate-400">
                                <Map size={48} className="mx-auto mb-4 text-slate-200" />
                                <p>Upload curriculum content to generate your personalized learning roadmap.</p>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                <p className="text-slate-500 text-sm mb-6">
                                    Your personalized <b className="text-violet-600">{roadmap[0]?.type || ''}</b> learning path based on mastery scores and prerequisite analysis.
                                </p>
                                {roadmap.map((milestone, i) => (
                                    <motion.div
                                        key={i}
                                        initial={{ opacity: 0, x: -12 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ delay: i * 0.1 }}
                                        className="flex gap-4 items-start"
                                    >
                                        {/* Step number */}
                                        <div className="flex flex-col items-center">
                                            <div className={`w-10 h-10 rounded-xl flex items-center justify-center font-extrabold text-sm shrink-0 ${
                                                milestone.type === 'Accelerated'
                                                    ? 'bg-violet-600 text-white'
                                                    : 'bg-teal-600 text-white'
                                            }`}>{i + 1}</div>
                                            {i < roadmap.length - 1 && <div className="w-px flex-1 bg-slate-200 mt-2 min-h-[24px]" />}
                                        </div>
                                        {/* Content */}
                                        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 flex-1 mb-4">
                                            <div className="flex items-center justify-between mb-1">
                                                <h4 className="font-bold text-slate-800">{milestone.phase}</h4>
                                                <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                                                    milestone.type === 'Accelerated'
                                                        ? 'bg-violet-100 text-violet-600'
                                                        : 'bg-teal-100 text-teal-600'
                                                }`}>{milestone.type}</span>
                                            </div>
                                            <p className="text-sm text-slate-500 mb-3">{milestone.focus}</p>
                                            <div className="flex flex-wrap gap-2">
                                                {milestone.topics.map((t, j) => (
                                                    <span key={j} className="text-xs bg-slate-50 border border-slate-100 text-slate-600 rounded-lg px-3 py-1 font-medium flex items-center gap-1">
                                                        <BookOpen size={10} />{t}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    </motion.div>
                                ))}
                            </div>
                        )}
                    </motion.div>
                )}

            </AnimatePresence>
        </div>
    );
};

export default Dashboard;
