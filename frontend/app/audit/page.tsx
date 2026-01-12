"use client";

import { useEffect, useState } from "react";
import { getAuditSessions, AuditSession } from "@/lib/api";
import AuditDetailModal from "@/components/AuditDetailModal";
import { RefreshCcw } from "lucide-react";

export default function AuditPage() {
    const [sessions, setSessions] = useState<AuditSession[]>([]);
    const [loading, setLoading] = useState(true);
    const [limit, setLimit] = useState(20);
    const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);

    useEffect(() => {
        fetchSessions();
    }, [limit]);

    async function fetchSessions() {
        setLoading(true);
        try {
            const data = await getAuditSessions(limit);
            setSessions(data);
        } catch (error) {
            console.error("Failed to fetch sessions:", error);
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="p-4 md:p-8">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
                <div>
                    <h1 className="text-3xl font-bold">审计日志</h1>
                    <p className="text-gray-400 mt-1">查看 Agent 执行历史</p>
                </div>
                <div className="flex w-full md:w-auto gap-4">
                    <select
                        value={limit}
                        onChange={(e) => setLimit(Number(e.target.value))}
                        className="flex-1 md:flex-none bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                    >
                        <option value={10}>最近 10 条</option>
                        <option value={20}>最近 20 条</option>
                        <option value={50}>最近 50 条</option>
                        <option value={100}>最近 100 条</option>
                    </select>
                    <button onClick={fetchSessions} className="btn btn-ghost flex items-center gap-2">
                        <RefreshCcw size={18} />
                        刷新
                    </button>
                </div>
            </div>

            <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
                {loading ? (
                    <div className="p-8 flex justify-center">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                    </div>
                ) : sessions.length === 0 ? (
                    <div className="p-8 text-center text-gray-500">暂无审计记录</div>
                ) : (
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>会话 ID</th>
                                <th>用户输入</th>
                                <th className="hidden md:table-cell">用户</th>
                                <th>状态</th>
                                <th className="hidden lg:table-cell">提供商</th>
                                <th className="hidden md:table-cell">耗时</th>
                                <th className="hidden sm:table-cell">时间</th>
                            </tr>
                        </thead>
                        <tbody>
                            {sessions.map((session) => (
                                <tr
                                    key={session.session_id}
                                    className="cursor-pointer hover:bg-gray-800/50 transition-colors"
                                    onClick={() => setSelectedSessionId(session.session_id)}
                                >
                                    <td className="font-mono text-sm text-gray-400">
                                        {session.session_id.slice(0, 8)}...
                                    </td>
                                    <td className="max-w-[150px] md:max-w-[300px] truncate">{session.input}</td>
                                    <td className="text-gray-400 hidden md:table-cell">{session.user}</td>
                                    <td>
                                        <span
                                            className={`badge ${session.status === "completed" ? "badge-dev" : "badge-prod"
                                                }`}
                                        >
                                            {session.status === "completed" ? "完成" : session.status}
                                        </span>
                                    </td>
                                    <td className="text-blue-400 hidden lg:table-cell">{session.provider || "-"}</td>
                                    <td className="text-gray-400 hidden md:table-cell">
                                        {session.total_duration_sec
                                            ? `${session.total_duration_sec.toFixed(2)}s`
                                            : "-"}
                                    </td>
                                    <td className="text-gray-400 text-sm hidden sm:table-cell">
                                        {new Date(session.timestamp).toLocaleString("zh-CN")}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>

            <div className="mt-4 text-gray-500 text-sm">
                显示 {sessions.length} 条记录
            </div>

            {selectedSessionId && (
                <AuditDetailModal
                    sessionId={selectedSessionId}
                    onClose={() => setSelectedSessionId(null)}
                />
            )}
        </div>
    );
}
