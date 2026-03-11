import type { Research, Source, Finding, ChatMessage, ResearchState, AgentStepsResponse, KnowledgeBaseResponse, ResearchNote } from '../types';

const API_BASE = '/api';

async function handleResponse<T>(response: Response): Promise<T> {
	if (!response.ok) {
		const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
		throw new Error(error.detail || `HTTP ${response.status}`);
	}
	return response.json();
}

export const api = {
	// Research endpoints
	async createResearch(query: string, notes?: string): Promise<Research> {
		const response = await fetch(`${API_BASE}/research`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ query, user_notes: notes }),
		});
		return handleResponse(response);
	},

	async listResearch(
		skip = 0,
		limit = 50,
		filters?: { status?: string; search?: string }
	): Promise<Research[]> {
		const params = new URLSearchParams({
			skip: skip.toString(),
			limit: limit.toString(),
		});

		if (filters?.status) {
			params.append('status', filters.status);
		}
		if (filters?.search) {
			params.append('search', filters.search);
		}

		const response = await fetch(`${API_BASE}/research?${params.toString()}`);
		return handleResponse(response);
	},

	async getResearch(id: number): Promise<Research> {
		const response = await fetch(`${API_BASE}/research/${id}`);
		return handleResponse(response);
	},

	async updateResearch(
		id: number,
		updates: { query?: string; user_notes?: string; tags?: string[] }
	): Promise<Research> {
		const response = await fetch(`${API_BASE}/research/${id}`, {
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(updates),
		});
		return handleResponse(response);
	},

	async cancelResearch(id: number): Promise<{ message: string }> {
		const response = await fetch(`${API_BASE}/research/${id}/cancel`, {
			method: 'POST',
		});
		return handleResponse(response);
	},

	async resumeResearch(id: number): Promise<{ message: string }> {
		const response = await fetch(`${API_BASE}/research/${id}/resume`, {
			method: 'POST',
		});
		return handleResponse(response);
	},

	async deleteResearch(id: number): Promise<void> {
		const response = await fetch(`${API_BASE}/research/${id}`, {
			method: 'DELETE',
		});
		if (!response.ok) throw new Error('Failed to delete research');
	},

	// Sources endpoints
	async getSources(researchId: number): Promise<Source[]> {
		const response = await fetch(`${API_BASE}/research/${researchId}/sources`);
		return handleResponse(response);
	},

	async createSource(researchId: number, source: {
		url: string;
		title?: string;
		author?: string;
		content_snippet?: string;
		source_type?: string;
		relevance_score?: number;
		user_notes?: string;
		tags?: string[];
	}): Promise<Source> {
		const response = await fetch(`${API_BASE}/research/${researchId}/sources`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(source),
		});
		return handleResponse(response);
	},

	async updateSource(
		researchId: number,
		sourceId: number,
		update: { user_notes?: string; tags?: string[]; title?: string }
	): Promise<Source> {
		const response = await fetch(`${API_BASE}/research/${researchId}/sources/${sourceId}`, {
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(update),
		});
		return handleResponse(response);
	},

	async deleteSource(researchId: number, sourceId: number): Promise<void> {
		const response = await fetch(`${API_BASE}/research/${researchId}/sources/${sourceId}`, {
			method: 'DELETE',
		});
		if (!response.ok) throw new Error('Failed to delete source');
	},

	// Findings endpoints
	async getFindings(researchId: number): Promise<Finding[]> {
		const response = await fetch(`${API_BASE}/research/${researchId}/findings`);
		return handleResponse(response);
	},

	async createFinding(researchId: number, finding: {
		content: string;
		source_ids?: number[];
	}): Promise<Finding> {
		const response = await fetch(`${API_BASE}/research/${researchId}/findings`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(finding),
		});
		return handleResponse(response);
	},

	async updateFinding(
		researchId: number,
		findingId: number,
		update: { content?: string; source_ids?: number[] }
	): Promise<Finding> {
		const response = await fetch(`${API_BASE}/research/${researchId}/findings/${findingId}`, {
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(update),
		});
		return handleResponse(response);
	},

	async deleteFinding(researchId: number, findingId: number): Promise<void> {
		const response = await fetch(`${API_BASE}/research/${researchId}/findings/${findingId}`, {
			method: 'DELETE',
		});
		if (!response.ok) throw new Error('Failed to delete finding');
	},

	// State endpoints
	async getState(researchId: number): Promise<ResearchState> {
		const response = await fetch(`${API_BASE}/research/${researchId}/state`);
		return handleResponse(response);
	},

	// Chat endpoints
	async sendChatMessage(researchId: number, message: string): Promise<ChatMessage> {
		const response = await fetch(`${API_BASE}/research/${researchId}/chat`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ message }),
		});
		return handleResponse(response);
	},

	async getChatHistory(researchId: number): Promise<ChatMessage[]> {
		const response = await fetch(`${API_BASE}/research/${researchId}/chat/history`);
		return handleResponse(response);
	},

	// Agent steps endpoint
	async getAgentSteps(researchId: number): Promise<AgentStepsResponse> {
		const response = await fetch(`${API_BASE}/research/${researchId}/steps`);
		return handleResponse(response);
	},

	// Knowledge base endpoint
	async getKnowledgeBase(researchId: number): Promise<KnowledgeBaseResponse> {
		const response = await fetch(`${API_BASE}/research/${researchId}/knowledge-base`);
		return handleResponse(response);
	},

	// Research notes endpoints
	async getNotes(researchId: number): Promise<ResearchNote[]> {
		const response = await fetch(`${API_BASE}/research/${researchId}/notes`);
		return handleResponse(response);
	},

	async createNote(researchId: number, note: { category: string; content: string }): Promise<ResearchNote> {
		const response = await fetch(`${API_BASE}/research/${researchId}/notes`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ ...note, agent: 'user' }),
		});
		return handleResponse(response);
	},

	async updateNote(researchId: number, noteId: number, update: { content?: string; category?: string }): Promise<ResearchNote> {
		const response = await fetch(`${API_BASE}/research/${researchId}/notes/${noteId}`, {
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(update),
		});
		return handleResponse(response);
	},

	async deleteNote(researchId: number, noteId: number): Promise<void> {
		const response = await fetch(`${API_BASE}/research/${researchId}/notes/${noteId}`, {
			method: 'DELETE',
		});
		if (!response.ok) throw new Error('Failed to delete note');
	},
};

export function createWebSocket(researchId: number): WebSocket {
	const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
	const wsUrl = `${protocol}//${window.location.host}/ws/research/${researchId}`;
	return new WebSocket(wsUrl);
}
