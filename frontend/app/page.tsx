"use client";

import { useEffect, useState } from "react";
import { getStats, getAuditSessions, Stats, AuditSession } from "@/lib/api";
import Link from "next/link";
import { Monitor, Network, Settings, Shield, Bot } from "lucide-react";

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [sessions, setSessions] = useState<AuditSession[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const [statsData, sessionsData] = await Promise.all([
          getStats(),
          getAuditSessions(5),
        ]);
        setStats(statsData);
        setSessions(sessionsData);
      } catch (error) {
        console.error("Failed to fetch data:", error);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  const statCards = [
    { label: "主机数量", value: stats?.hosts_count || 0, icon: Monitor, color: "from-blue-500 to-blue-600", href: "/hosts" },
    { label: "跳板机", value: stats?.jumps_count || 0, icon: Network, color: "from-purple-500 to-purple-600", href: "/jumps" },
    { label: "服务配置", value: stats?.services_count || 0, icon: Settings, color: "from-green-500 to-green-600", href: "/services" },
    { label: "策略规则", value: stats?.policies_count || 0, icon: Shield, color: "from-orange-500 to-orange-600", href: "/policies" },
  ];

  return (
    <div className="p-4 md:p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold">仪表盘</h1>
        <p className="text-gray-400 mt-1">FlowPilot 系统概览</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {statCards.map((card) => (
          <Link
            key={card.label}
            href={card.href}
            className="card-hover bg-gray-900 rounded-xl p-6 border border-gray-800"
          >
            <div className="flex items-center justify-between mb-4">
              <span className="text-3xl text-gray-500">
                <card.icon size={32} />
              </span>
              <div className={`px-3 py-1 rounded-full bg-gradient-to-r ${card.color} text-white text-sm font-medium`}>
                {card.value}
              </div>
            </div>
            <h3 className="text-gray-400 text-sm">{card.label}</h3>
          </Link>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* AI Chat Card */}
        <Link
          href="/chat"
          className="card-hover bg-gradient-to-br from-blue-600 to-purple-600 rounded-xl p-6"
        >
          <div className="flex items-center gap-4">
            <Bot size={48} className="text-white opacity-90" />
            <div>
              <h3 className="text-xl font-bold text-white">AI 对话</h3>
              <p className="text-blue-100 mt-1">
                使用自然语言管理服务器
              </p>
            </div>
          </div>
        </Link>

        {/* Quick Stats */}
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
          <h3 className="text-lg font-semibold mb-4">会话统计</h3>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-3xl font-bold">{stats?.sessions_count || 0}</p>
              <p className="text-gray-400 text-sm">总会话数</p>
            </div>
            <Link href="/audit" className="btn btn-ghost">
              查看全部 →
            </Link>
          </div>
        </div>
      </div>

      {/* Recent Sessions */}
      <div className="bg-gray-900 rounded-xl border border-gray-800">
        <div className="p-6 border-b border-gray-800 flex justify-between items-center">
          <h3 className="text-lg font-semibold">最近会话</h3>
          <Link href="/audit" className="text-blue-400 hover:text-blue-300 text-sm">
            查看全部
          </Link>
        </div>
        <div className="divide-y divide-gray-800">
          {sessions.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              暂无会话记录
            </div>
          ) : (
            sessions.map((session) => (
              <div key={session.session_id} className="p-4 hover:bg-gray-800/50 transition">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <p className="text-white font-medium truncate">{session.input}</p>
                    <div className="flex items-center gap-3 mt-2 text-sm text-gray-400">
                      <span>{session.user}</span>
                      <span>•</span>
                      <span>{new Date(session.timestamp).toLocaleString("zh-CN")}</span>
                      {session.provider && (
                        <>
                          <span>•</span>
                          <span className="text-blue-400">{session.provider}</span>
                        </>
                      )}
                    </div>
                  </div>
                  <span
                    className={`badge ${session.status === "completed" ? "badge-dev" : "badge-prod"
                      }`}
                  >
                    {session.status === "completed" ? "完成" : session.status}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
