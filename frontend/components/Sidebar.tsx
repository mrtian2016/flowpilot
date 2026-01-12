"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Monitor, Network, Settings, Shield, FileText, Bot, Rocket } from "lucide-react";

const navItems = [
    { href: "/", label: "仪表盘", icon: LayoutDashboard },
    { href: "/hosts", label: "主机管理", icon: Monitor },
    { href: "/jumps", label: "跳板机", icon: Network },
    { href: "/services", label: "服务配置", icon: Settings },
    { href: "/policies", label: "策略规则", icon: Shield },
    { href: "/audit", label: "审计日志", icon: FileText },
    { href: "/chat", label: "AI 对话", icon: Bot },
];

export default function Sidebar() {
    const pathname = usePathname();

    return (
        <aside className="w-64 bg-gray-900 min-h-screen flex flex-col border-r border-gray-800">
            {/* Logo */}
            <div className="p-6 border-b border-gray-800">
                <h1 className="text-2xl font-bold text-white flex items-center gap-2" suppressHydrationWarning>
                    <Rocket className="w-8 h-8 text-blue-500" />
                    <span className="bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
                        FlowPilot
                    </span>
                </h1>
                <p className="text-gray-500 text-sm mt-1">DevOps AI Agent</p>
            </div>

            {/* Navigation */}
            <nav className="flex-1 p-4">
                <ul className="space-y-1">
                    {navItems.map((item) => {
                        const isActive = pathname === item.href;
                        return (
                            <li key={item.href}>
                                <Link
                                    href={item.href}
                                    className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 ${isActive
                                        ? "bg-blue-600 text-white shadow-lg shadow-blue-500/25"
                                        : "text-gray-400 hover:bg-gray-800 hover:text-white"
                                        }`}
                                >
                                    <span className="text-lg">
                                        <item.icon size={20} />
                                    </span>
                                    <span className="font-medium">{item.label}</span>
                                </Link>
                            </li>
                        );
                    })}
                </ul>
            </nav>

            {/* Footer */}
            <div className="p-4 border-t border-gray-800">
                <div className="text-gray-500 text-xs text-center">
                    FlowPilot v0.1.0
                </div>
            </div>
        </aside>
    );
}
