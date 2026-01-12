"use client";

import { useState, useEffect } from "react";
import Sidebar from "./Sidebar";
import { usePathname } from "next/navigation";
import { X, Menu } from "lucide-react";

export default function LayoutWrapper({ children }: { children: React.ReactNode }) {
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);
    const pathname = usePathname();

    // Close sidebar on route change
    useEffect(() => {
        setIsSidebarOpen(false);
    }, [pathname]);

    return (
        <div className="flex h-screen bg-gray-950 text-white overflow-hidden">
            {/* Desktop Sidebar */}
            <div className="hidden md:block">
                <Sidebar />
            </div>

            {/* Mobile Sidebar (Drawer) */}
            <div
                className={`fixed inset-0 z-50 transform transition-transform duration-300 md:hidden ${isSidebarOpen ? "translate-x-0" : "-translate-x-full"
                    }`}
            >
                <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setIsSidebarOpen(false)} />
                <div className="relative w-64 h-full shadow-2xl">
                    <Sidebar />
                    <button
                        onClick={() => setIsSidebarOpen(false)}
                        className="absolute top-4 right-4 text-gray-400 hover:text-white md:hidden"
                    >
                        <X size={24} />
                    </button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
                {/* Mobile Header */}
                <div className="md:hidden flex items-center justify-between p-4 border-b border-gray-800 bg-gray-900/50 backdrop-blur-sm">
                    <button
                        onClick={() => setIsSidebarOpen(true)}
                        className="text-gray-400 hover:text-white p-2 -ml-2 rounded-lg hover:bg-gray-800"
                    >
                        <Menu size={24} />
                    </button>
                    <span className="font-bold text-lg bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
                        FlowPilot
                    </span>
                    <div className="w-8" /> {/* Spacer for centering */}
                </div>

                <main className="flex-1 overflow-auto bg-gray-950 relative">
                    {children}
                </main>
            </div>
        </div>
    );
}
