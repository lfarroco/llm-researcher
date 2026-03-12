export interface Research {
	id: number;
	query: string;
	result?: string;
	status: 'pending' | 'researching' | 'completed' | 'failed' | 'error' | 'cancelled';
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
	research_id?: number;
	source_ids?: number[];
	content: string;
	category?: string;
	importance?: number;
	user_notes?: string;
	created_by?: string;
	created_at: string;
	updated_at?: string;
}

export interface ChatMessage {
	id: number;
	research_id: number;
	role: 'user' | 'assistant';
	content: string;
	created_at: string;
}

export interface WebSocketEvent {
	event_type: 'connected' | 'status_change' | 'source_added' | 'finding_created' | 'error' | 'completed';
	data: any;
	timestamp: string;
}

export interface ResearchState {
	current_step?: string;
	subqueries?: string[];
	sources_found?: number;
	[key: string]: any;
}

export interface ResearchPlanProgressItem {
	status: 'completed' | 'pending';
	finding?: string | null;
}

export interface ResearchPlan {
	query: string;
	refined_question?: string | null;
	sub_queries: string[];
	progress: Record<string, ResearchPlanProgressItem>;
	outline?: string | null;
}

export interface ResearchPlanUpdatePayload {
	add_queries?: string[];
	remove_queries?: string[];
	refined_question?: string;
}

export interface AgentStep {
	timestamp: string;
	step_type: 'planning' | 'searching' | 'relevance_filter' | 'thinking' | 'hypothesis' | 'synthesis' | 'formatting' | 'summary' | 'error';
	title: string;
	description: string;
	status: 'running' | 'completed' | 'skipped' | 'error';
	metadata: Record<string, any>;
}

export interface AgentStepsResponse {
	research_id: number;
	status: string;
	steps: AgentStep[];
	total_steps: number;
}

export interface KBCitation {
	id: string;
	title: string;
	url: string;
	source_type: string;
	relevance_score: number;
	author?: string;
	snippet: string;
}

export interface SubQueryGroup {
	sub_query: string;
	status: string;
	error?: string;
	citation_count: number;
	citations: KBCitation[];
}

export interface KBHypothesis {
	title: string;
	description: string;
	status: string;
	metadata: Record<string, unknown>;
}

export interface KnowledgeBaseResponse {
	research_id: number;
	query: string;
	status: string;
	sub_queries: string[];
	sub_query_groups: SubQueryGroup[];
	unassigned_citations: KBCitation[];
	hypotheses: KBHypothesis[];
	total_citations: number;
	source_type_distribution: Record<string, number>;
}

export interface ResearchNote {
	id: number;
	research_id: number;
	agent: string;
	category: string;
	content: string;
	created_at: string;
	updated_at: string;
}

export interface ExtractedEntity {
	name: string;
	entity_type: 'method' | 'material' | 'metric' | 'finding' | 'concept' | string;
	mentions: string[];
	mention_count: number;
}

export interface ResearchEntitiesResponse {
	research_id: number;
	status: string;
	total_entities: number;
	entities: ExtractedEntity[];
}

export interface AppSetting {
	key: string;
	type: 'string' | 'integer' | 'number' | 'boolean';
	sensitive: boolean;
	value: string | number | boolean;
	default_value: string | number | boolean;
	source: 'env' | 'db';
}
