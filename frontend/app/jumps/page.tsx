"use client";

import { useEffect, useState } from "react";
import { getJumps, deleteJump, Jump } from "@/lib/api";
import { Plus } from "lucide-react";

export default function JumpsPage() {
    const [jumps, setJumps] = useState<Jump[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchJumps();
    }, []);

    async function fetchJumps() {
        setLoading(true);
        try {
            const data = await getJumps();
            setJumps(data);
        } catch (error) {
            console.error("Failed to fetch jumps:", error);
        } finally {
            setLoading(false);
        }
    }

    async function handleDelete(name: string) {
        if (!confirm(`确定要删除跳板机 "${name}" 吗？`)) return;
        try {
            await deleteJump(name);
            fetchJumps();
        } catch (error) {
            console.error("Failed to delete jump:", error);
        }
    }

    return (
        <div className="p-4 md:p-8">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
                <div>
                    <h1 className="text-3xl font-bold">跳板机管理</h1>
                    <p className="text-gray-400 mt-1">管理 SSH 跳板机配置</p>
                </div>
                <button className="btn btn-primary w-full md:w-auto flex items-center gap-2 justify-center">
                    <Plus size={18} />
                    添加跳板机
                </button>
            </div>

            <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
                {loading ? (
                    <div className="p-8 flex justify-center">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                    </div>
                ) : jumps.length === 0 ? (
                    <div className="p-8 text-center text-gray-500">
                        暂无跳板机配置
                    </div>
                ) : (
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>名称</th>
                                <th>地址</th>
                                <th className="hidden md:table-cell">用户</th>
                                <th className="hidden md:table-cell">端口</th>
                                <th className="text-right">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {jumps.map((jump) => (
                                <tr key={jump.id}>
                                    <td className="font-medium">
                                        {jump.name}
                                        <div className="md:hidden text-xs text-gray-500 mt-1">
                                            {jump.user}@{jump.addr}:{jump.port}
                                        </div>
                                    </td>
                                    <td className="text-gray-400 hidden md:table-cell">{jump.addr}</td>
                                    <td className="text-gray-400 hidden md:table-cell">{jump.user}</td>
                                    <td className="text-gray-400 hidden md:table-cell">{jump.port}</td>
                                    <td className="text-right">
                                        <button className="btn btn-ghost text-sm mr-2">编辑</button>
                                        <button
                                            onClick={() => handleDelete(jump.name)}
                                            className="btn btn-ghost text-sm text-red-400 hover:text-red-300"
                                        >
                                            删除
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>

            <div className="mt-4 text-gray-500 text-sm">共 {jumps.length} 个跳板机</div>
        </div>
    );
}
