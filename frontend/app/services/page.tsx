"use client";

import { useEffect, useState } from "react";
import { getServices, deleteService, Service } from "@/lib/api";

export default function ServicesPage() {
    const [services, setServices] = useState<Service[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchServices();
    }, []);

    async function fetchServices() {
        setLoading(true);
        try {
            const data = await getServices();
            setServices(data);
        } catch (error) {
            console.error("Failed to fetch services:", error);
        } finally {
            setLoading(false);
        }
    }

    async function handleDelete(name: string) {
        if (!confirm(`确定要删除服务 "${name}" 吗？`)) return;
        try {
            await deleteService(name);
            fetchServices();
        } catch (error) {
            console.error("Failed to delete service:", error);
        }
    }

    return (
        <div className="p-8">
            <div className="flex justify-between items-center mb-8">
                <div>
                    <h1 className="text-3xl font-bold">服务配置</h1>
                    <p className="text-gray-400 mt-1">管理应用服务配置</p>
                </div>
                <button className="btn btn-primary">
                    <span>+</span> 添加服务
                </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {loading ? (
                    <div className="col-span-full p-8 flex justify-center">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                    </div>
                ) : services.length === 0 ? (
                    <div className="col-span-full p-8 text-center text-gray-500">
                        暂无服务配置
                    </div>
                ) : (
                    services.map((service) => (
                        <div
                            key={service.id}
                            className="card-hover bg-gray-900 rounded-xl border border-gray-800 p-6"
                        >
                            <div className="flex items-start justify-between mb-4">
                                <div>
                                    <h3 className="text-lg font-semibold">{service.name}</h3>
                                    <p className="text-gray-400 text-sm mt-1">
                                        {service.description || "暂无描述"}
                                    </p>
                                </div>
                                <span className="text-2xl">⚙️</span>
                            </div>

                            <div className="text-sm text-gray-500 mb-4">
                                配置项: {Object.keys(service.config_json).length} 个
                            </div>

                            <div className="flex gap-2">
                                <button className="btn btn-ghost text-sm flex-1">查看</button>
                                <button
                                    onClick={() => handleDelete(service.name)}
                                    className="btn btn-ghost text-sm text-red-400"
                                >
                                    删除
                                </button>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}
