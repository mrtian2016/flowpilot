"use client";

import { useEffect, useState } from "react";
import { getPolicies, deletePolicy, Policy } from "@/lib/api";
import { Plus } from "lucide-react";

export default function PoliciesPage() {
    const [policies, setPolicies] = useState<Policy[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchPolicies();
    }, []);

    async function fetchPolicies() {
        setLoading(true);
        try {
            const data = await getPolicies();
            setPolicies(data);
        } catch (error) {
            console.error("Failed to fetch policies:", error);
        } finally {
            setLoading(false);
        }
    }

    async function handleDelete(name: string) {
        if (!confirm(`确定要删除策略 "${name}" 吗？`)) return;
        try {
            await deletePolicy(name);
            fetchPolicies();
        } catch (error) {
            console.error("Failed to delete policy:", error);
        }
    }

    const effectColors: Record<string, string> = {
        allow: "badge-dev",
        require_confirm: "badge-staging",
        deny: "badge-prod",
    };

    const effectLabels: Record<string, string> = {
        allow: "允许",
        require_confirm: "需确认",
        deny: "拒绝",
    };

    return (
        <div className="p-4 md:p-8">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
                <div>
                    <h1 className="text-3xl font-bold">策略规则</h1>
                    <p className="text-gray-400 mt-1">管理安全策略和权限控制</p>
                </div>
                <button className="btn btn-primary w-full md:w-auto flex items-center gap-2 justify-center">
                    <Plus size={18} />
                    添加策略
                </button>
            </div>

            <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
                {loading ? (
                    <div className="p-8 flex justify-center">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                    </div>
                ) : policies.length === 0 ? (
                    <div className="p-8 text-center text-gray-500">
                        暂无策略配置
                    </div>
                ) : (
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>名称</th>
                                <th className="hidden md:table-cell">条件</th>
                                <th>效果</th>
                                <th className="hidden lg:table-cell">消息</th>
                                <th className="text-right">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {policies.map((policy) => (
                                <tr key={policy.id}>
                                    <td className="font-medium">
                                        {policy.name}
                                        <div className="md:hidden text-xs text-gray-500 mt-1 truncate max-w-[150px]">
                                            {policy.message}
                                        </div>
                                    </td>
                                    <td className="text-gray-400 hidden md:table-cell">
                                        <code className="bg-gray-800 px-2 py-1 rounded text-xs">
                                            {JSON.stringify(policy.condition).slice(0, 50)}...
                                        </code>
                                    </td>
                                    <td>
                                        <span className={`badge ${effectColors[policy.effect] || ""}`}>
                                            {effectLabels[policy.effect] || policy.effect}
                                        </span>
                                    </td>
                                    <td className="text-gray-400 max-w-[300px] truncate hidden lg:table-cell">
                                        {policy.message}
                                    </td>
                                    <td className="text-right">
                                        <button className="btn btn-ghost text-sm mr-2">编辑</button>
                                        <button
                                            onClick={() => handleDelete(policy.name)}
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

            <div className="mt-4 text-gray-500 text-sm">共 {policies.length} 条策略</div>
        </div>
    );
}
