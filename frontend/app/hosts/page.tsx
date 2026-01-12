"use client";

import { useEffect, useState } from "react";
import { getHosts, deleteHost, createHost, Host } from "@/lib/api";
import HostServiceModal from "@/components/HostServiceModal";
import { Plus, RefreshCcw, Search } from "lucide-react";

interface HostFormData {
    name: string;
    addr: string;
    user: string;
    port: number;
    env: string;
    description: string;
    group: string;
    jump: string;
    ssh_key: string;
    tags: string[];
}

const defaultFormData: HostFormData = {
    name: "",
    addr: "",
    user: "root",
    port: 22,
    env: "dev",
    description: "",
    group: "default",
    jump: "",
    ssh_key: "",
    tags: [],
};

export default function HostsPage() {
    const [hosts, setHosts] = useState<Host[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState({ env: "", group: "" });
    const [searchQuery, setSearchQuery] = useState("");
    const [showModal, setShowModal] = useState(false);
    const [editingHost, setEditingHost] = useState<Host | null>(null);
    const [formData, setFormData] = useState<HostFormData>(defaultFormData);
    const [saving, setSaving] = useState(false);
    const [serviceModalHost, setServiceModalHost] = useState<Host | null>(null);

    useEffect(() => {
        fetchHosts();
    }, []);

    async function fetchHosts() {
        setLoading(true);
        try {
            const data = await getHosts(filter.env || undefined, filter.group || undefined, searchQuery || undefined);
            setHosts(data);
        } catch (error) {
            console.error("Failed to fetch hosts:", error);
        } finally {
            setLoading(false);
        }
    }

    async function handleDelete(name: string) {
        if (!confirm(`确定要删除主机 "${name}" 吗？`)) return;
        try {
            await deleteHost(name);
            fetchHosts();
        } catch (error) {
            console.error("Failed to delete host:", error);
        }
    }

    function openAddModal() {
        setEditingHost(null);
        setFormData(defaultFormData);
        setShowModal(true);
    }

    function openEditModal(host: Host) {
        setEditingHost(host);
        setFormData({
            name: host.name,
            addr: host.addr,
            user: host.user,
            port: host.port,
            env: host.env,
            description: host.description,
            group: host.group,
            jump: host.jump || "",
            ssh_key: host.ssh_key || "",
            tags: host.tags,
        });
        setShowModal(true);
    }

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        setSaving(true);

        try {
            const payload = {
                ...formData,
                jump: formData.jump || null,
                ssh_key: formData.ssh_key || null,
            };

            if (editingHost) {
                // 更新主机
                const res = await fetch(`/api/hosts/${editingHost.name}`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                if (!res.ok) throw new Error("更新失败");
            } else {
                // 创建主机
                await createHost(payload as Omit<Host, "id">);
            }

            setShowModal(false);
            fetchHosts();
        } catch (error) {
            console.error("保存失败:", error);
            alert("保存失败，请重试");
        } finally {
            setSaving(false);
        }
    }

    const envColors: Record<string, string> = {
        dev: "badge-dev",
        staging: "badge-staging",
        prod: "badge-prod",
    };

    const groups = [...new Set(hosts.map((h) => h.group))];

    return (
        <div className="p-4 md:p-8">
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
                <div>
                    <h1 className="text-3xl font-bold">主机管理</h1>
                    <p className="text-gray-400 mt-1">管理 SSH 主机配置</p>
                </div>
                <button onClick={openAddModal} className="btn btn-primary w-full md:w-auto flex items-center gap-2 justify-center">
                    <Plus size={18} />
                    添加主机
                </button>
            </div>

            {/* Filters & Search */}
            <div className="flex flex-col md:flex-row gap-4 mb-6">
                {/* Search Input */}
                <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                    <input
                        type="text"
                        placeholder="搜索主机名、IP、描述..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && fetchHosts()}
                        className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-10 pr-4 py-2 text-white focus:outline-none focus:border-blue-500 placeholder-gray-500"
                    />
                </div>

                <div className="flex gap-4 overflow-x-auto pb-1 md:pb-0">
                    <select
                        value={filter.env}
                        onChange={(e) => setFilter({ ...filter, env: e.target.value })}
                        className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                    >
                        <option value="">所有环境</option>
                        <option value="dev">开发环境</option>
                        <option value="staging">预发布</option>
                        <option value="prod">生产环境</option>
                    </select>
                    <select
                        value={filter.group}
                        onChange={(e) => setFilter({ ...filter, group: e.target.value })}
                        className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                    >
                        <option value="">所有分组</option>
                        {groups.map((g) => (
                            <option key={g} value={g}>
                                {g}
                            </option>
                        ))}
                    </select>
                    <button onClick={fetchHosts} className="btn btn-ghost w-full md:w-auto flex items-center gap-2 justify-center whitespace-nowrap">
                        <RefreshCcw size={18} />
                        刷新
                    </button>
                </div>
            </div>

            {/* Table */}
            <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
                {loading ? (
                    <div className="p-8 flex justify-center">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                    </div>
                ) : hosts.length === 0 ? (
                    <div className="p-8 text-center text-gray-500">暂无主机配置</div>
                ) : (
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>名称</th>
                                <th className="hidden md:table-cell">地址</th>
                                <th className="hidden lg:table-cell">用户</th>
                                <th>环境</th>
                                <th className="hidden xl:table-cell">分组</th>
                                <th className="hidden lg:table-cell">备注</th>
                                <th className="text-right">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {hosts.map((host) => (
                                <tr key={host.id}>
                                    <td className="font-medium">
                                        {host.name}
                                        {/* Mobile only info */}
                                        <div className="md:hidden text-xs text-gray-500 mt-1">
                                            {host.addr}:{host.port}
                                        </div>
                                    </td>
                                    <td className="text-gray-400 hidden md:table-cell">
                                        {host.addr}:{host.port}
                                    </td>
                                    <td className="text-gray-400 hidden lg:table-cell">{host.user}</td>
                                    <td>
                                        <span className={`badge ${envColors[host.env] || ""}`}>
                                            {host.env}
                                        </span>
                                    </td>
                                    <td className="text-gray-400 hidden xl:table-cell">{host.group}</td>
                                    <td className="text-gray-400 max-w-[200px] truncate hidden lg:table-cell">
                                        {host.description}
                                    </td>
                                    <td className="text-right">
                                        <button
                                            onClick={() => setServiceModalHost(host)}
                                            className="btn btn-ghost text-sm mr-2 text-blue-400 hover:text-blue-300"
                                        >
                                            服务
                                        </button>
                                        <button
                                            onClick={() => openEditModal(host)}
                                            className="btn btn-ghost text-sm mr-2"
                                        >
                                            编辑
                                        </button>
                                        <button
                                            onClick={() => handleDelete(host.name)}
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

            <div className="mt-4 text-gray-500 text-sm">共 {hosts.length} 台主机</div>

            {/* Modal */}
            {showModal && (
                <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
                    <div className="bg-gray-900 rounded-xl border border-gray-800 w-full max-w-lg max-h-[90vh] overflow-y-auto">
                        <div className="p-6 border-b border-gray-800">
                            <h2 className="text-xl font-semibold">
                                {editingHost ? "编辑主机" : "添加主机"}
                            </h2>
                        </div>

                        <form onSubmit={handleSubmit} className="p-6 space-y-4">
                            {/* 名称 */}
                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-1">
                                    主机别名 *
                                </label>
                                <input
                                    type="text"
                                    value={formData.name}
                                    onChange={(e) =>
                                        setFormData({ ...formData, name: e.target.value })
                                    }
                                    disabled={!!editingHost}
                                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 disabled:opacity-50"
                                    placeholder="例如：ubuntu-prod-1"
                                    required
                                />
                            </div>

                            {/* 地址 */}
                            <div className="grid grid-cols-3 gap-4">
                                <div className="col-span-2">
                                    <label className="block text-sm font-medium text-gray-300 mb-1">
                                        地址 *
                                    </label>
                                    <input
                                        type="text"
                                        value={formData.addr}
                                        onChange={(e) =>
                                            setFormData({ ...formData, addr: e.target.value })
                                        }
                                        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                                        placeholder="IP 或域名"
                                        required
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-300 mb-1">
                                        端口
                                    </label>
                                    <input
                                        type="number"
                                        value={formData.port}
                                        onChange={(e) =>
                                            setFormData({ ...formData, port: Number(e.target.value) })
                                        }
                                        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                                    />
                                </div>
                            </div>

                            {/* 用户 */}
                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-1">
                                    SSH 用户名 *
                                </label>
                                <input
                                    type="text"
                                    value={formData.user}
                                    onChange={(e) =>
                                        setFormData({ ...formData, user: e.target.value })
                                    }
                                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                                    required
                                />
                            </div>

                            {/* 环境和分组 */}
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-300 mb-1">
                                        环境
                                    </label>
                                    <select
                                        value={formData.env}
                                        onChange={(e) =>
                                            setFormData({ ...formData, env: e.target.value })
                                        }
                                        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                                    >
                                        <option value="dev">开发环境</option>
                                        <option value="staging">预发布</option>
                                        <option value="prod">生产环境</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-300 mb-1">
                                        分组
                                    </label>
                                    <input
                                        type="text"
                                        value={formData.group}
                                        onChange={(e) =>
                                            setFormData({ ...formData, group: e.target.value })
                                        }
                                        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                                        placeholder="default"
                                    />
                                </div>
                            </div>

                            {/* 跳板机 */}
                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-1">
                                    跳板机（可选）
                                </label>
                                <input
                                    type="text"
                                    value={formData.jump}
                                    onChange={(e) =>
                                        setFormData({ ...formData, jump: e.target.value })
                                    }
                                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                                    placeholder="跳板机别名"
                                />
                            </div>

                            {/* SSH Key */}
                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-1">
                                    SSH 密钥路径（可选）
                                </label>
                                <input
                                    type="text"
                                    value={formData.ssh_key}
                                    onChange={(e) =>
                                        setFormData({ ...formData, ssh_key: e.target.value })
                                    }
                                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                                    placeholder="~/.ssh/id_rsa"
                                />
                            </div>

                            {/* 备注 */}
                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-1">
                                    备注
                                </label>
                                <textarea
                                    value={formData.description}
                                    onChange={(e) =>
                                        setFormData({ ...formData, description: e.target.value })
                                    }
                                    rows={2}
                                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 resize-none"
                                    placeholder="描述这台主机..."
                                />
                            </div>

                            {/* 按钮 */}
                            <div className="flex justify-end gap-3 pt-4">
                                <button
                                    type="button"
                                    onClick={() => setShowModal(false)}
                                    className="btn btn-ghost"
                                >
                                    取消
                                </button>
                                <button
                                    type="submit"
                                    disabled={saving}
                                    className={`btn btn-primary ${saving ? "opacity-50" : ""}`}
                                >
                                    {saving ? "保存中..." : editingHost ? "保存修改" : "添加主机"}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Host Service Modal */}
            {serviceModalHost && (
                <HostServiceModal
                    hostName={serviceModalHost.name}
                    hostDescription={serviceModalHost.description}
                    onClose={() => setServiceModalHost(null)}
                />
            )}
        </div>
    );
}
