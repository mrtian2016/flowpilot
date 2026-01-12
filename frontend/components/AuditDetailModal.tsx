"use client";

import { useEffect, useState } from "react";
import { AuditSessionDetail, getAuditSessionDetail } from "@/lib/api";

interface AuditDetailModalProps {
    sessionId: string;
    onClose: () => void;
}

export default function AuditDetailModal({ sessionId, onClose }: AuditDetailModalProps) {
    const [detail, setDetail] = useState<AuditSessionDetail | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchDetail();
    }, [sessionId]);

    async function fetchDetail() {
        setLoading(true);
        try {
            const data = await getAuditSessionDetail(sessionId);
            setDetail(data);
        } catch (error) {
            console.error("Failed to fetch session detail:", error);
        } finally {
            setLoading(false);
        }
    }

    if (!sessionId) return null;

    return (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
            <div className="bg-gray-900 rounded-xl border border-gray-800 w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
                {/* Header */}
                <div className="p-6 border-b border-gray-800 flex justify-between items-center">
                    <div>
                        <h2 className="text-xl font-semibold">会话详情</h2>
                        <p className="text-gray-400 text-sm mt-1 font-mono">{sessionId}</p>
                    </div>
                    <button onClick={onClose} className="text-gray-400 hover:text-white text-2xl">
                        ×
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6">
                    {loading ? (
                        <div className="flex justify-center py-8">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                        </div>
                    ) : detail ? (
                        <div className="space-y-6">
                            {/* Meta Info */}
                            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
                                <div className="bg-gray-800 p-3 rounded-lg">
                                    <div className="text-gray-400 mb-1">用户</div>
                                    <div>{detail.user}</div>
                                </div>
                                <div className="bg-gray-800 p-3 rounded-lg">
                                    <div className="text-gray-400 mb-1">时间</div>
                                    <div>{new Date(detail.timestamp).toLocaleString("zh-CN")}</div>
                                </div>
                                <div className="bg-gray-800 p-3 rounded-lg">
                                    <div className="text-gray-400 mb-1">状态</div>
                                    <div>
                                        <span className={`badge ${detail.status === "completed" ? "badge-dev" : "badge-prod"}`}>
                                            {detail.status}
                                        </span>
                                    </div>
                                </div>
                                <div className="bg-gray-800 p-3 rounded-lg">
                                    <div className="text-gray-400 mb-1">耗时</div>
                                    <div>{detail.total_duration_sec?.toFixed(2)}s</div>
                                </div>
                            </div>

                            {/* Input */}
                            <div>
                                <h3 className="text-sm font-semibold text-gray-400 mb-2 uppercase tracking-wider">
                                    用户输入
                                </h3>
                                <div className="bg-gray-800 p-4 rounded-lg text-white">
                                    {detail.input}
                                </div>
                            </div>

                            {/* Agent Reasoning */}
                            {detail.agent_reasoning && (
                                <div>
                                    <h3 className="text-sm font-semibold text-gray-400 mb-2 uppercase tracking-wider">
                                        Agent 推理
                                    </h3>
                                    <div className="bg-gray-800 p-4 rounded-lg text-gray-300 whitespace-pre-wrap">
                                        {detail.agent_reasoning}
                                    </div>
                                </div>
                            )}

                            {/* Tool Calls */}
                            <div>
                                <h3 className="text-sm font-semibold text-gray-400 mb-2 uppercase tracking-wider">
                                    执行记录 ({detail.tool_calls.length})
                                </h3>
                                {detail.tool_calls.length === 0 ? (
                                    <div className="text-gray-500 text-sm italic">无工具调用记录</div>
                                ) : (
                                    <div className="space-y-3">
                                        {detail.tool_calls.map((call) => (
                                            <div key={call.call_id} className="bg-gray-800 rounded-lg overflow-hidden border border-gray-700">
                                                {/* Tool Header */}
                                                <div className="px-4 py-3 bg-gray-800/50 flex justify-between items-center border-b border-gray-700">
                                                    <div className="flex items-center gap-3">
                                                        <span className="font-mono text-blue-400 font-semibold">
                                                            {call.tool_name}
                                                        </span>
                                                        <span className={`text-xs px-2 py-0.5 rounded ${call.status === "success"
                                                            ? "bg-green-500/10 text-green-400"
                                                            : "bg-red-500/10 text-red-400"
                                                            }`}>
                                                            {call.status}
                                                        </span>
                                                    </div>
                                                    <div className="text-xs text-gray-500 font-mono">
                                                        {call.duration_sec ? `${call.duration_sec.toFixed(2)}s` : ""}
                                                    </div>
                                                </div>

                                                {/* Tool Args */}
                                                <div className="p-4 bg-gray-900/50 border-b border-gray-700">
                                                    <div className="text-xs text-gray-500 mb-1">参数:</div>
                                                    <pre className="text-sm text-gray-300 overflow-x-auto whitespace-pre-wrap font-mono">
                                                        {JSON.stringify(call.tool_args, null, 2)}
                                                    </pre>
                                                </div>

                                                {/* Tool Output */}
                                                {(call.stdout_summary || call.error) && (
                                                    <div className="p-4 bg-black/20">
                                                        <div className="text-xs text-gray-500 mb-1">输出:</div>
                                                        <pre className="text-xs text-gray-400 overflow-x-auto whitespace-pre-wrap font-mono max-h-60 scrollbar-thin">
                                                            {call.stdout_summary || call.error}
                                                        </pre>
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>

                            {/* Final Output */}
                            {detail.final_output && (
                                <div>
                                    <h3 className="text-sm font-semibold text-gray-400 mb-2 uppercase tracking-wider">
                                        最终回复
                                    </h3>
                                    <div className="bg-gray-800 p-4 rounded-lg text-white whitespace-pre-wrap">
                                        {detail.final_output}
                                    </div>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="text-center text-red-400 py-8">无法加载会话详情</div>
                    )}
                </div>
            </div>
        </div>
    );
}
