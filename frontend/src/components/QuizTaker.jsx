import React, { useState } from 'react';
import { motion } from 'framer-motion';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const QuizTaker = ({ data, onComplete }) => {
    const [currentQ, setCurrentQ] = useState(0);
    const [score, setScore] = useState(0);
    const [selectedOption, setSelectedOption] = useState(null);
    const [showResult, setShowResult] = useState(false);
    const [isAnswered, setIsAnswered] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);

    // Track detailed results for backend
    const [results, setResults] = useState({
        topic: data.topic || "General Quiz",
        weak_subtopics: []
    });

    const questions = data.questions;
    const currentQuestion = questions[currentQ];

    const handleOptionClick = (option) => {
        if (isAnswered) return;
        setSelectedOption(option);
        setIsAnswered(true);

        if (option === currentQuestion.correct) {
            setScore(prev => prev + 1);
        } else {
            // Track incorrect answer topics
            setResults(prev => ({
                ...prev,
                weak_subtopics: [...prev.weak_subtopics, currentQuestion.learning_objective || "General"]
            }));
        }
    };

    const nextQuestion = () => {
        if (currentQ < questions.length - 1) {
            setCurrentQ(prev => prev + 1);
            setSelectedOption(null);
            setIsAnswered(false);
        } else {
            finishQuiz();
        }
    };

    const finishQuiz = async () => {
        setShowResult(true);
        setIsSubmitting(true);

        // Determine final score
        // Note: 'score' state might lag one render if we did it inside handleOptionClick for the last question,
        // but here we are in nextQuestion after the click, so score is updated.

        const finalResult = {
            topic: data.topic || "Unknown Topic",
            score: score, // This might miss the LAST point if logic was different, but here handleOptionClick happens separately.
            total_questions: questions.length,
            date: new Date().toISOString(),
            weak_subtopics: results.weak_subtopics
        };

        try {
            await axios.post(`${API_BASE}/quiz/submit`, finalResult);
            console.log("Quiz saved successfully");
        } catch (e) {
            console.error("Failed to save quiz", e);
        } finally {
            setIsSubmitting(false);
        }
    };

    if (showResult) {
        return (
            <div className="text-center p-8 bg-white rounded-xl shadow-sm border border-slate-100 max-w-2xl mx-auto">
                <div className="w-20 h-20 bg-teal-100 text-teal-600 rounded-full flex items-center justify-center mx-auto mb-6 text-3xl"></div>
                <h3 className="text-2xl font-bold text-slate-800 mb-2">Quiz Completed!</h3>
                <p className="text-slate-500 mb-6">You scored {score} out of {questions.length}</p>

                <div className="w-full bg-slate-100 rounded-full h-4 mb-4 overflow-hidden">
                    <div className="bg-teal-500 h-full transition-all duration-1000" style={{ width: `${(score / questions.length) * 100}%` }}></div>
                </div>

                {isSubmitting ? (
                    <p className="text-xs text-slate-400 mb-8">Saving results...</p>
                ) : (
                    <p className="text-xs text-green-600 mb-8">Results saved to your profile!</p>
                )}

                <button onClick={onComplete} className="btn-primary">Back to Menu</button>
            </div>
        );
    }

    return (
        <div className="max-w-2xl mx-auto text-left">
            <div className="flex justify-between items-center mb-6">
                <span className="text-sm font-bold text-slate-404 uppercase tracking-wider">Question {currentQ + 1}/{questions.length}</span>
                <span className="text-sm font-bold text-teal-600">Score: {score}</span>
            </div>

            <div className="mb-8">
                <h3 className="text-xl font-bold text-slate-800 mb-6">{currentQuestion.question}</h3>
                <div className="space-y-3">
                    {currentQuestion.options.map((opt, idx) => {
                        let stateClass = "border-slate-200 hover:border-teal-300 hover:bg-slate-50";
                        if (isAnswered) {
                            if (opt === currentQuestion.correct) stateClass = "border-green-500 bg-green-50 text-green-700";
                            else if (opt === selectedOption) stateClass = "border-red-500 bg-red-50 text-red-700";
                            else stateClass = "border-slate-100 opacity-50";
                        } else if (selectedOption === opt) {
                            stateClass = "border-teal-500 bg-teal-50";
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

            {isAnswered && (
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="p-4 bg-blue-50 text-blue-800 rounded-lg mb-6 text-sm">
                    <b>Explanation:</b> {currentQuestion.correct} is the correct answer.
                </motion.div>
            )}

            <div className="flex justify-end">
                <button
                    onClick={nextQuestion}
                    disabled={!isAnswered}
                    className={`btn-primary ${!isAnswered && 'opacity-50 cursor-not-allowed'}`}
                >
                    {currentQ === questions.length - 1 ? 'Finish Quiz' : 'Next Question'}
                </button>
            </div>
        </div>
    );
};

export default QuizTaker;
