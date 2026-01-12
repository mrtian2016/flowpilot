// API 客户端
const API_BASE = "";

export interface Host {
    id: number;
    name: string;
    addr: string;
    user: string;
    port: number;
    env: string;
    description: string;
    group: string;
    jump: string | null;
    ssh_key: string | null;
    tags: string[];
}

export interface Jump {
    id: number;
    name: string;
    addr: string;
    user: string;
    port: number;
}

export interface Service {
    id: number;
    name: string;
    description: string;
    config_json: Record<string, unknown>;
}

export interface Policy {
    id: number;
    name: string;
    condition: Record<string, unknown>;
    effect: string;
    message: string;
}

export interface AuditSession {
    session_id: string;
    timestamp: string;
    user: string;
    input: string;
    status: string;
    provider: string | null;
    total_duration_sec: number | null;
}

export interface Stats {
    hosts_count: number;
    jumps_count: number;
    services_count: number;
    policies_count: number;
    sessions_count: number;
}

// Hosts
export async function getHosts(env?: string, group?: string): Promise<Host[]> {
    const params = new URLSearchParams();
    if (env) params.set("env", env);
    if (group) params.set("group", group);
    const res = await fetch(`${API_BASE}/api/hosts?${params}`);
    if (!res.ok) throw new Error("Failed to fetch hosts");
    return res.json();
}

export async function createHost(data: Omit<Host, "id">): Promise<Host> {
    const res = await fetch(`${API_BASE}/api/hosts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Failed to create host");
    return res.json();
}

export async function deleteHost(name: string): Promise<void> {
    const res = await fetch(`${API_BASE}/api/hosts/${name}`, {
        method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to delete host");
}

export async function updateHost(name: string, data: Partial<Host>): Promise<Host> {
    const res = await fetch(`${API_BASE}/api/hosts/${name}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Failed to update host");
    return res.json();
}

// Jumps
export async function getJumps(): Promise<Jump[]> {
    const res = await fetch(`${API_BASE}/api/jumps`);
    if (!res.ok) throw new Error("Failed to fetch jumps");
    return res.json();
}

export async function createJump(data: Omit<Jump, "id">): Promise<Jump> {
    const res = await fetch(`${API_BASE}/api/jumps`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Failed to create jump");
    return res.json();
}

export async function deleteJump(name: string): Promise<void> {
    const res = await fetch(`${API_BASE}/api/jumps/${name}`, {
        method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to delete jump");
}

// Services
export async function getServices(): Promise<Service[]> {
    const res = await fetch(`${API_BASE}/api/services`);
    if (!res.ok) throw new Error("Failed to fetch services");
    return res.json();
}

export async function deleteService(name: string): Promise<void> {
    const res = await fetch(`${API_BASE}/api/services/${name}`, {
        method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to delete service");
}

// Policies
export async function getPolicies(): Promise<Policy[]> {
    const res = await fetch(`${API_BASE}/api/policies`);
    if (!res.ok) throw new Error("Failed to fetch policies");
    return res.json();
}

export async function deletePolicy(name: string): Promise<void> {
    const res = await fetch(`${API_BASE}/api/policies/${name}`, {
        method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to delete policy");
}

// Audit Sessions
export async function getAuditSessions(limit = 20): Promise<AuditSession[]> {
    const res = await fetch(`${API_BASE}/api/audit/sessions?limit=${limit}`);
    if (!res.ok) throw new Error("Failed to fetch audit sessions");
    return res.json();
}

// Stats
export async function getStats(): Promise<Stats> {
    const res = await fetch(`${API_BASE}/api/stats`);
    if (!res.ok) throw new Error("Failed to fetch stats");
    return res.json();
}

// Chat
export interface ChatMessage {
    role: "user" | "assistant" | "system";
    content: string;
}

export interface ChatResponse {
    id: string;
    choices: Array<{
        message: {
            role: string;
            content: string;
        };
        finish_reason: string;
    }>;
}

export async function sendChatMessage(
    messages: ChatMessage[],
    model = "gemini"
): Promise<ChatResponse> {
    const res = await fetch(`${API_BASE}/v1/chat/completions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            model,
            messages,
            stream: false,
        }),
    });
    if (!res.ok) throw new Error("Failed to send chat message");
    return res.json();
}
