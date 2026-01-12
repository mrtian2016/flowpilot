"use client";

import { useState, useEffect } from "react";
import {
    HostService,
    getHostServices,
    createHostService,
    updateHostService,
    deleteHostService,
} from "@/lib/api";

interface HostServiceModalProps {
    hostName: string;
    hostDescription: string;
    onClose: () => void;
}

interface ServiceFormData {
    name: string;
    service_name: string;
    service_type: string;
    description: string;
}

const defaultFormData: ServiceFormData = {
    name: "",
    service_name: "",
    service_type: "systemd",
    description: "",
};

export default function HostServiceModal({
    hostName,
    hostDescription,
    onClose,
}: HostServiceModalProps) {
    const [services, setServices] = useState<HostService[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [editingService, setEditingService] = useState<HostService | null>(null);
    const [formData, setFormData] = useState<ServiceFormData>(defaultFormData);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        fetchServices();
    }, [hostName]);

    async function fetchServices() {
        setLoading(true);
        try {
            const data = await getHostServices(hostName);
            setServices(data);
        } catch (error) {
            console.error("Failed to fetch services:", error);
        } finally {
            setLoading(false);
        }
    }

    function openAddForm() {
        setEditingService(null);
        setFormData(defaultFormData);
        setShowForm(true);
    }

    function openEditForm(service: HostService) {
        setEditingService(service);
        setFormData({
            name: service.name,
            service_name: service.service_name,
            service_type: service.service_type,
            description: service.description,
        });
        setShowForm(true);
    }

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        setSaving(true);

        try {
            if (editingService) {
                await updateHostService(hostName, editingService.id, formData);
            } else {
                await createHostService(hostName, formData);
            }
            setShowForm(false);
            fetchServices();
        } catch (error) {
            console.error("保存失败:", error);
            alert("保存失败，请重试");
        } finally {
            setSaving(false);
        }
    }

    async function handleDelete(service: HostService) {
        if (!confirm(`确定要删除服务 "${service.name}" 吗？`)) return;
        try {
            await deleteHostService(hostName, service.id);
            fetchServices();
        } catch (error) {
            console.error("删除失败:", error);
        }
    }

    const serviceTypeLabels: Record<string, string> = {
        systemd: "Systemd",
        docker: "Docker",
        pm2: "PM2",
    };

    return (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
            <div className="bg-gray-900 rounded-xl border border-gray-800 w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
                {/* Header */}
                <div className="p-6 border-b border-gray-800 flex justify-between items-center">
                    <div>
                        <h2 className="text-xl font-semibold">主机服务管理</h2>
                        <p className="text-gray-400 text-sm mt-1">
                            {hostDescription || hostName}
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-white text-2xl"
                    >
                        ×
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6">
                    {loading ? (
                        <div className="flex justify-center py-8">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                        </div>
                    ) : showForm ? (
                        /* Form */
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-1">
                                    服务名称 *
                                </label>
                                <input
                                    type="text"
                                    value={formData.name}
                                    onChange={(e) =>
                                        setFormData({ ...formData, name: e.target.value })
                                    }
                                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                                    placeholder="用户友好名称，如：后端服务"
                                    required
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-1">
                                    服务标识 *
                                </label>
                                <input
                                    type="text"
                                    value={formData.service_name}
                                    onChange={(e) =>
                                        setFormData({ ...formData, service_name: e.target.value })
                                    }
                                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                                    placeholder="系统服务名，如：ir_web.service"
                                    required
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-1">
                                    服务类型
                                </label>
                                <select
                                    value={formData.service_type}
                                    onChange={(e) =>
                                        setFormData({ ...formData, service_type: e.target.value })
                                    }
                                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                                >
                                    <option value="systemd">Systemd (systemctl)</option>
                                    <option value="docker">Docker 容器</option>
                                    <option value="pm2">PM2 (Node.js)</option>
                                </select>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-1">
                                    描述
                                </label>
                                <textarea
                                    value={formData.description}
                                    onChange={(e) =>
                                        setFormData({ ...formData, description: e.target.value })
                                    }
                                    rows={2}
                                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 resize-none"
                                    placeholder="服务描述..."
                                />
                            </div>

                            <div className="flex justify-end gap-3 pt-4">
                                <button
                                    type="button"
                                    onClick={() => setShowForm(false)}
                                    className="btn btn-ghost"
                                >
                                    取消
                                </button>
                                <button
                                    type="submit"
                                    disabled={saving}
                                    className={`btn btn-primary ${saving ? "opacity-50" : ""}`}
                                >
                                    {saving
                                        ? "保存中..."
                                        : editingService
                                            ? "保存修改"
                                            : "添加服务"}
                                </button>
                            </div>
                        </form>
                    ) : (
                        /* Service List */
                        <div>
                            <div className="flex justify-between items-center mb-4">
                                <span className="text-gray-400">
                                    共 {services.length} 个服务
                                </span>
                                <button onClick={openAddForm} className="btn btn-primary text-sm">
                                    + 添加服务
                                </button>
                            </div>

                            {services.length === 0 ? (
                                <div className="text-center text-gray-500 py-8">
                                    <p>暂无服务配置</p>
                                    <p className="text-sm mt-2">
                                        添加服务后，可以使用 AI 命令控制这些服务
                                    </p>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {services.map((service) => (
                                        <div
                                            key={service.id}
                                            className="bg-gray-800 rounded-lg p-4 border border-gray-700"
                                        >
                                            <div className="flex justify-between items-start">
                                                <div>
                                                    <div className="flex items-center gap-2">
                                                        <span className="font-medium">{service.name}</span>
                                                        <span className="badge badge-dev text-xs">
                                                            {serviceTypeLabels[service.service_type] ||
                                                                service.service_type}
                                                        </span>
                                                    </div>
                                                    <div className="text-gray-400 text-sm mt-1 font-mono">
                                                        {service.service_name}
                                                    </div>
                                                    {service.description && (
                                                        <div className="text-gray-500 text-sm mt-2">
                                                            {service.description}
                                                        </div>
                                                    )}
                                                </div>
                                                <div className="flex gap-2">
                                                    <button
                                                        onClick={() => openEditForm(service)}
                                                        className="btn btn-ghost text-sm"
                                                    >
                                                        编辑
                                                    </button>
                                                    <button
                                                        onClick={() => handleDelete(service)}
                                                        className="btn btn-ghost text-sm text-red-400"
                                                    >
                                                        删除
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
