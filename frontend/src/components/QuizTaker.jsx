import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE;

const QuizTaker = ({ data, onComplete }) => {
    const [currentQ, setCurrentQ] = useState(0);
    const [score, setScore] = useState(0);
    const [selectedOption, setSelectedOption] = useState(null);
    const [showResult, setShowResult] = useState(false);
    const [isAnswered, setIsAnswered] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [promoInfo, setPromoInfo] = useState(null);

    // Telemetry States
    const [quizStartTime] = useState(Date.now());
    const [elapsedSeconds, setElapsedSeconds] = useState(0);
    const [questionStartTime, setQuestionStartTime] = useState(Date.now());
    const [totalResponseDuration, setTotalResponseDuration] = useState(0);

    const [hintsRevealed, setHintsRevealed] = useState(0);
    const [totalHintsUsed, setTotalHintsUsed] = useState(0);

    const [answerChangesForQuestion, setAnswerChangesForQuestion] = useState(0);
    const [totalAnswerChanges, setTotalAnswerChanges] = useState(0);

    // Track detailed results for backend
    const [results, setResults] = useState({
        topic: data.topic || "General Quiz",
        weak_subtopics: []
    });

    const questions = data.questions;
    const currentQuestion = questions[currentQ];

    // Quiz overall elapsed seconds timer
    useEffect(() => {
        const timer = setInterval(() => {
            setElapsedSeconds(Math.floor((Date.now() - quizStartTime) / 1000));
        }, 1000);
        return () => clearInterval(timer);
    }, [quizStartTime]);

    // Question start time logger
    useEffect(() => {
        setQuestionStartTime(Date.now());
    }, [currentQ]);

    const formatTime = (totalSeconds) => {
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;
        return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    };

    const handleOptionClick = (option) => {
        if (isAnswered) return;

        if (selectedOption === null) {
            setSelectedOption(option);
        } else if (selectedOption !== option) {
            setSelectedOption(option);
            setAnswerChangesForQuestion(prev => prev + 1);
        }
    };

    const handleRevealHint = () => {
        if (hintsRevealed < 2) {
            setHintsRevealed(prev => prev + 1);
            setTotalHintsUsed(prev => prev + 1);
        }
    };

    const handleSubmitAnswer = () => {
        setIsAnswered(true);

        if (selectedOption === currentQuestion.correct) {
            setScore(prev => prev + 1);
        } else {
            // Track incorrect answer topics
            setResults(prev => ({
                ...prev,
                weak_subtopics: [...prev.weak_subtopics, currentQuestion.learning_objective || "General"]
            }));
        }

        // Accumulate telemetry
        setTotalAnswerChanges(prev => prev + answerChangesForQuestion);
        const questionDuration = (Date.now() - questionStartTime) / 1000;
        setTotalResponseDuration(prev => prev + questionDuration);
    };

    const nextQuestion = () => {
        if (currentQ < questions.length - 1) {
            setCurrentQ(prev => prev + 1);
            setSelectedOption(null);
            setIsAnswered(false);
            setHintsRevealed(0);
            setAnswerChangesForQuestion(0);
        } else {
            finishQuiz();
        }
    };

    const finishQuiz = async () => {
        setShowResult(true);
        setIsSubmitting(true);

        const finalResult = {
            topic: data.topic || "Unknown Topic",
            score: score, 
            total_questions: questions.length,
            date: new Date().toISOString(),
            weak_subtopics: results.weak_subtopics,
            difficulty: data.difficulty || "Beginner",
            response_duration: Math.round(totalResponseDuration),
            hints_used: totalHintsUsed,
            answer_changes_before_submit: totalAnswerChanges
        };

        try {
            const res = await axios.post(`${API_BASE}/quiz/submit`, finalResult);
            console.log("Quiz saved successfully with telemetry:", res.data);
            if (res.data && res.data.auto_promoted) {
                setPromoInfo(res.data.new_level);
            }
        } catch (e) {
            console.error("Failed to save quiz", e);
        } finally {
            setIsSubmitting(false);
        }
    };

    if (showResult) {
        return (
            <div className="text-center p-8 bg-white rounded-xl shadow-sm border border-slate-100 max-w-2xl mx-auto">
                <div className="w-20 h-20 bg-teal-100 text-teal-600 rounded-full flex items-center justify-center mx-auto mb-6 text-3xl">🎉</div>
                
                {promoInfo && (
                    <div className="mb-6 p-4 rounded-xl border border-teal-200 bg-teal-50 text-teal-800 shadow-sm animate-pulse">
                        <h4 className="font-bold text-lg">✨ Cognitive Promotion!</h4>
                        <p className="text-xs leading-relaxed mt-1 font-semibold">
                            Outstanding consecutive score! You have been automatically promoted to the <b>{promoInfo} Tier</b>.
                        </p>
                    </div>
                )}
                
                <h3 className="text-2xl font-bold text-slate-800 mb-2">Quiz Completed!</h3>
                <p className="text-slate-500 mb-6 font-medium">You scored {score} out of {questions.length}</p>

                <div className="grid grid-cols-3 gap-4 mb-6 bg-slate-50 p-4 rounded-xl border border-slate-100 text-slate-600">
                    <div>
                        <p className="text-[10px] uppercase font-bold text-slate-400">Total Duration</p>
                        <p className="text-sm font-bold text-slate-700">{formatTime(Math.round(totalResponseDuration))}</p>
                    </div>
                    <div>
                        <p className="text-[10px] uppercase font-bold text-slate-400">Hints Revealed</p>
                        <p className="text-sm font-bold text-slate-700">{totalHintsUsed} hints</p>
                    </div>
                    <div>
                        <p className="text-[10px] uppercase font-bold text-slate-400">Answer Changes</p>
                        <p className="text-sm font-bold text-slate-700">{totalAnswerChanges} edits</p>
                    </div>
                </div>

                <div className="w-full bg-slate-100 rounded-full h-4 mb-4 overflow-hidden">
                    <div className="bg-teal-500 h-full transition-all duration-1000" style={{ width: `${(score / questions.length) * 100}%` }}></div>
                </div>

                {isSubmitting ? (
                    <p className="text-xs text-slate-400 mb-8">Saving results...</p>
                ) : (
                    <p className="text-xs text-green-600 mb-8 font-semibold">Results and cognitive telemetry successfully synced with your profile!</p>
                )}

                <button onClick={onComplete} className="btn-primary">Back to Menu</button>
            </div>
        );
    }

    return (
        <div className="max-w-2xl mx-auto text-left">
            {/* Telemetry HUD display */}
            <div className="flex flex-wrap justify-between items-center gap-4 mb-6 bg-slate-50 p-4 rounded-xl border border-slate-200">
                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Question {currentQ + 1} / {questions.length}</span>
                <span className="text-xs font-bold text-teal-600">Time Spent: {formatTime(elapsedSeconds)}</span>
                <span className="text-xs font-bold text-amber-600">Hints: {totalHintsUsed}</span>
                <span className="text-xs font-bold text-indigo-600">Edits: {totalAnswerChanges}</span>
                <span className="text-xs font-bold text-teal-600 bg-teal-50 px-2.5 py-1 rounded">Score: {score}</span>
            </div>

            <div className="mb-8">
                <h3 className="text-xl font-bold text-slate-800 mb-6 leading-relaxed">{currentQuestion.question}</h3>
                <div className="space-y-3">
                    {currentQuestion.options.map((opt, idx) => {
                        let stateClass = "border-slate-200 hover:border-teal-300 hover:bg-slate-50";
                        if (isAnswered) {
                            if (opt === currentQuestion.correct) stateClass = "border-green-500 bg-green-50 text-green-700";
                            else if (opt === selectedOption) stateClass = "border-red-500 bg-red-50 text-red-700";
                            else stateClass = "border-slate-100 opacity-50";
                        } else if (selectedOption === opt) {
                            stateClass = "border-teal-500 bg-teal-50 text-teal-700";
                        }

                        return (
                            <div
                                key={idx}
                                onClick={() => handleOptionClick(opt)}
                                className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${stateClass}`}
                            >
                                {opt}
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Hint Display Panel */}
            {hintsRevealed >= 1 && (
                <div className="p-3.5 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg text-xs leading-relaxed mb-3">
                    <b>Hint 1:</b> {currentQuestion.hint_1 || "Think about the core concepts of this lesson."}
                </div>
            )}
            {hintsRevealed >= 2 && (
                <div className="p-3.5 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg text-xs leading-relaxed mb-4">
                    <b>Hint 2:</b> {currentQuestion.hint_2 || "Focus on the textbook context clues."}
                </div>
            )}

            {isAnswered && (
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="p-4 bg-blue-50 text-blue-800 rounded-lg mb-6 text-sm border border-blue-100">
                    <b>Explanation:</b> {currentQuestion.correct} is the correct answer.
                </motion.div>
            )}

            <div className="flex justify-between items-center mt-6">
                <div>
                    {!isAnswered && (
                        <button
                            onClick={handleRevealHint}
                            disabled={hintsRevealed >= 2}
                            className="px-4 py-2 border border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100 disabled:opacity-50 text-xs font-bold rounded-lg transition-all focus:outline-none flex items-center gap-1.5"
                        >
                            💡 Get Hint ({hintsRevealed}/2)
                        </button>
                    )}
                </div>
                <div className="flex gap-2">
                    {!isAnswered ? (
                        <button
                            onClick={handleSubmitAnswer}
                            disabled={selectedOption === null}
                            className={`btn-primary ${selectedOption === null ? 'opacity-50 cursor-not-allowed' : ''}`}
                        >
                            Submit Answer
                        </button>
                    ) : (
                        <button
                            onClick={nextQuestion}
                            className="btn-primary"
                        >
                            {currentQ === questions.length - 1 ? 'Finish Quiz' : 'Next Question'}
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};

export default QuizTaker;
