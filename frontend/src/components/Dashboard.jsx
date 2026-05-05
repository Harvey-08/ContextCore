import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import {
    Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer,
    BarChart, Bar, XAxis, YAxis, Tooltip
} from 'recharts';
import { Brain, Activity, TrendingUp, AlertTriangle, BookOpen, ChevronRight } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const Dashboard = ({ onBack }) => {
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState(null);

    useEffect(() => {
        fetchAnalytics();
    }, []);

    const fetchAnalytics = async () => {
        try {
            const res = await axios.get(`${API_BASE}/dashboard/analytics`);
            setData(res.data);
        } catch (error) {
            console.error("Failed to fetch analytics", error);
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="min-h-[600px] flex items-center justify-center">
                <div className="loader-spinner"></div>
            </div>
        );
    }

    if (!data || !data.spider_data || data.spider_data.length === 0) {
        return (
            <div className="min-h-[500px] flex flex-col items-center justify-center text-center p-8">
                <div className="w-24 h-24 bg-slate-100 rounded-full flex items-center justify-center mb-6 text-slate-300">
                    <Activity size={48} />
                </div>
                <h2 className="text-2xl font-bold text-slate-700 mb-2">No Data Available</h2>
                <p className="text-slate-500 max-w-md mb-8">
                    Take a few quizzes to generate your personalized learning analytics and knowledge graph.
                </p>
                <button onClick={onBack} className="btn-primary">Go to Content Generator</button>
            </div>
        );
    }

    return (
        <div className="pt-24 px-6 max-w-7xl mx-auto pb-20">
            <div className="mb-8 flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-slate-800">Learning Insights</h1>
                    <p className="text-slate-500">Track your proficiency and focus on weak areas</p>
                </div>
                <button onClick={onBack} className="text-sm font-medium text-slate-500 hover:text-teal-600">
                    Back to Generator
                </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

                {/* Spider Chart Card */}
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="lg:col-span-1 glass-panel p-6 flex flex-col">
                    <div className="flex items-center gap-3 mb-6">
                        <div className="w-10 h-10 bg-purple-100 text-purple-600 rounded-lg flex items-center justify-center">
                            <Brain size={20} />
                        </div>
                        <h3 className="font-bold text-slate-700">Topic Proficiency</h3>
                    </div>

                    <div className="flex-1 min-h-[300px] -ml-6">
                        <ResponsiveContainer width="100%" height="100%">
                            <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data.spider_data}>
                                <PolarGrid stroke="#e2e8f0" />
                                <PolarAngleAxis dataKey="subject" tick={{ fill: '#64748b', fontSize: 12 }} />
                                <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                                <Radar
                                    name="Proficiency"
                                    dataKey="A"
                                    stroke="#8b5cf6"
                                    strokeWidth={3}
                                    fill="#8b5cf6"
                                    fillOpacity={0.3}
                                />
                                <Tooltip />
                            </RadarChart>
                        </ResponsiveContainer>
                    </div>
                    <div className="mt-4 text-center text-xs text-slate-400">
                        Based on your quiz performance history
                    </div>
                </motion.div>

                {/* Recommendations / Weak Areas */}
                <div className="lg:col-span-2 space-y-6">

                    {/* Weakest Topics Alert */}
                    {data.weakest_topics.length > 0 && (
                        <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 }} className="bg-red-50 border border-red-100 rounded-xl p-6">
                            <div className="flex items-start gap-4">
                                <div className="mt-1 text-red-500">
                                    <AlertTriangle size={24} />
                                </div>
                                <div>
                                    <h3 className="font-bold text-red-800 text-lg mb-1">Attention Needed</h3>
                                    <p className="text-red-600/80 text-sm mb-4">
                                        You are struggling with <b>{data.weakest_topics[0].topic}</b> (Score: {data.weakest_topics[0].score}%).
                                        We recommend reviewing the core concepts.
                                    </p>
                                </div>
                            </div>
                        </motion.div>
                    )}

                    {/* AI Recommendations */}
                    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="glass-panel p-6">
                        <div className="flex items-center gap-3 mb-6">
                            <div className="w-10 h-10 bg-teal-100 text-teal-600 rounded-lg flex items-center justify-center">
                                <TrendingUp size={20} />
                            </div>
                            <h3 className="font-bold text-slate-700">AI Recommended Focus</h3>
                        </div>

                        <div className="grid gap-4">
                            {data.recommendations.length === 0 ? (
                                <div className="text-center p-8 text-slate-400">
                                    Good job! No critical weak areas detected yet.
                                </div>
                            ) : (
                                data.recommendations.map((rec, idx) => (
                                    <div key={idx} className="bg-white border border-slate-100 rounded-xl p-4 shadow-sm hover:shadow-md transition-shadow">
                                        <div className="flex justify-between items-start mb-2">
                                            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Improve {rec.topic}</span>
                                        </div>
                                        <p className="text-slate-700 font-medium mb-3">{rec.suggestion}</p>

                                        {rec.sources && rec.sources.length > 0 && (
                                            <div className="bg-slate-50 rounded-lg p-3 text-sm">
                                                <div className="text-xs font-bold text-slate-500 mb-2 flex items-center gap-1">
                                                    <BookOpen size={12} /> Suggested Readings
                                                </div>
                                                {rec.sources.map((src, i) => (
                                                    <div key={i} className="mb-1 last:mb-0 text-slate-600 truncate"> {src.topic}</div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                ))
                            )}
                        </div>
                    </motion.div>

                </div>
            </div>
        </div>
    );
};

export default Dashboard;
