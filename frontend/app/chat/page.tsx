"use client";

import { useState, useRef, useEffect } from "react";
import { ChatMessage, sendChatMessage } from "@/lib/api";
import ReactMarkdown from "react-markdown";

interface Message {
    role: "user" | "assistant";
    content: string;
    timestamp: Date;
}

export default function ChatPage() {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [model, setModel] = useState("gemini");
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    async function handleSend() {
        if (!input.trim() || loading) return;

        const userMessage: Message = {
            role: "user",
            content: input,
            timestamp: new Date(),
        };

        setMessages((prev) => [...prev, userMessage]);
        setInput("");
        setLoading(true);

        try {
            // 构建 API 消息格式
            const apiMessages: ChatMessage[] = messages.map((m) => ({
                role: m.role,
                content: m.content,
            }));
            apiMessages.push({ role: "user", content: input });

            const response = await sendChatMessage(apiMessages, model);

            const assistantMessage: Message = {
                role: "assistant",
                content: response.choices[0]?.message?.content || "无响应",
                timestamp: new Date(),
            };

            setMessages((prev) => [...prev, assistantMessage]);
        } catch (error) {
            console.error("Failed to send message:", error);
            const errorMessage: Message = {
                role: "assistant",
                content: "❌ 发送失败，请检查后端服务是否正常运行。",
                timestamp: new Date(),
            };
            setMessages((prev) => [...prev, errorMessage]);
        } finally {
            setLoading(false);
        }
    }

    function handleKeyDown(e: React.KeyboardEvent) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    }

    function clearChat() {
        setMessages([]);
    }

    return (
        <div className="flex flex-col h-screen">
            {/* Header */}
            <div className="flex-shrink-0 border-b border-gray-800 bg-gray-900 p-4">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-xl font-bold flex items-center gap-2">
                            <span className="text-2xl">🤖</span> AI 对话
                        </h1>
                        <p className="text-gray-500 text-sm">使用自然语言管理服务器</p>
                    </div>
                    <div className="flex items-center gap-4">
                        <select
                            value={model}
                            onChange={(e) => setModel(e.target.value)}
                            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                        >
                            <option value="gemini">Gemini</option>
                            <option value="claude">Claude</option>
                            <option value="zhipu">智谱</option>
                        </select>
                        <button onClick={clearChat} className="btn btn-ghost text-sm">
                            🗑️ 清空
                        </button>
                    </div>
                </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-auto p-4 space-y-4">
                {messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-gray-500">
                        <span className="text-6xl mb-4">💬</span>
                        <p className="text-lg">开始对话</p>
                        <p className="text-sm mt-2">试试问：&quot;查看 ubuntu 服务器运行时间&quot;</p>
                    </div>
                ) : (
                    messages.map((message, index) => (
                        <div
                            key={index}
                            className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                        >
                            <div
                                className={`max-w-[80%] rounded-2xl px-4 py-3 ${message.role === "user"
                                        ? "bg-blue-600 text-white"
                                        : "bg-gray-800 text-gray-100"
                                    }`}
                            >
                                {message.role === "assistant" ? (
                                    <div className="prose prose-invert prose-sm max-w-none">
                                        <ReactMarkdown>{message.content}</ReactMarkdown>
                                    </div>
                                ) : (
                                    <p className="whitespace-pre-wrap">{message.content}</p>
                                )}
                                <p
                                    className={`text-xs mt-2 ${message.role === "user" ? "text-blue-200" : "text-gray-500"
                                        }`}
                                >
                                    {message.timestamp.toLocaleTimeString("zh-CN")}
                                </p>
                            </div>
                        </div>
                    ))
                )}

                {loading && (
                    <div className="flex justify-start">
                        <div className="bg-gray-800 rounded-2xl px-4 py-3">
                            <div className="flex items-center gap-2">
                                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
                                <span className="text-gray-400">思考中...</span>
                            </div>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="flex-shrink-0 border-t border-gray-800 bg-gray-900 p-4">
                <div className="flex gap-4">
                    <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="输入消息... (Enter 发送，Shift+Enter 换行)"
                        rows={2}
                        className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 resize-none"
                    />
                    <button
                        onClick={handleSend}
                        disabled={loading || !input.trim()}
                        className={`btn px-6 ${loading || !input.trim()
                                ? "bg-gray-700 text-gray-500 cursor-not-allowed"
                                : "btn-primary"
                            }`}
                    >
                        发送
                    </button>
                </div>
            </div>
        </div>
    );
}
