export interface Research {
	id: number;
	query: string;
	result?: string;
	status: 'pending' | 'researching' | 'completed' | 'failed';
	user_notes?: string;
	tags?: string[];
	created_at: string;
	updated_at: string;
}

export interface Source {
	id: number;
	research_id: number;
	title: string;
	url: string;
	content_snippet?: string;
	source_type: string;
	author?: string;
	relevance_score: number;
	user_notes?: string;
	tags?: string[];
	accessed_at: string;
}

export interface Finding {
	id: number;
	research_id: number;
	source_id?: number;
	content: string;
	category?: string;
	importance?: number;
	user_notes?: string;
	created_at: string;
}

export interface ChatMessage {
	id: number;
	research_id: number;
	role: 'user' | 'assistant';
	content: string;
	created_at: string;
}

export interface WebSocketEvent {
	event_type: 'connected' | 'status_change' | 'source_added' | 'finding_created' | 'progress' | 'error' | 'completed';
	data: any;
	timestamp: string;
}

export interface ResearchState {
	current_step?: string;
	subqueries?: string[];
	sources_found?: number;
	[key: string]: any;
}
