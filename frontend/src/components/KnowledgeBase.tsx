import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import type { KnowledgeBaseResponse, KBCitation, SubQueryGroup } from '../types';

interface Props {
	researchId: number;
}

type ViewMode = 'tree' | 'sources';

export default function KnowledgeBase({ researchId }: Props) {
	const [kb, setKb] = useState<KnowledgeBaseResponse | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [viewMode, setViewMode] = useState<ViewMode>('tree');
	const [expandedGroups, setExpandedGroups] = useState<Set<number>>(new Set());
	const [expandedCitation, setExpandedCitation] = useState<string | null>(null);
	const [filterType, setFilterType] = useState<string>('all');

	const loadKB = useCallback(async () => {
		try {
			const data = await api.getKnowledgeBase(researchId);
			setKb(data);
			setError(null);
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Failed to load knowledge base');
		} finally {
			setLoading(false);
		}
	}, [researchId]);

	useEffect(() => {
		loadKB();
	}, [researchId, loadKB]);

	const toggleGroup = (index: number) => {
		setExpandedGroups(prev => {
			const next = new Set(prev);
			if (next.has(index)) {
				next.delete(index);
			} else {
				next.add(index);
			}
			return next;
		});
	};

	const expandAll = () => {
		if (!kb) return;
		const allIndices = new Set(kb.sub_query_groups.map((_, i) => i));
		setExpandedGroups(allIndices);
	};

	const collapseAll = () => {
		setExpandedGroups(new Set());
	};

	const getSourceTypeColor = (type: string) => {
		switch (type) {
			case 'web': return 'bg-blue-100 text-blue-700';
			case 'arxiv': return 'bg-purple-100 text-purple-700';
			case 'wikipedia': return 'bg-green-100 text-green-700';
			case 'pubmed': return 'bg-red-100 text-red-700';
			case 'semantic_scholar': return 'bg-yellow-100 text-yellow-700';
			default: return 'bg-gray-100 text-gray-700';
		}
	};

	const getSourceTypeIcon = (type: string) => {
		switch (type) {
			case 'web': return '🌐';
			case 'arxiv': return '📄';
			case 'wikipedia': return '📖';
			case 'pubmed': return '🏥';
			case 'semantic_scholar': return '🎓';
			default: return '📌';
		}
	};

	const getRelevanceBar = (score: number) => {
		const pct = Math.round(score * 100);
		const color = score >= 0.7 ? 'bg-green-400' : score >= 0.4 ? 'bg-yellow-400' : 'bg-red-400';
		return (
			<div className="flex items-center gap-1.5">
				<div className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
					<div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
				</div>
				<span className="text-xs text-gray-500">{pct}%</span>
			</div>
		);
	};

	const renderCitation = (c: KBCitation) => {
		const isExpanded = expandedCitation === c.url;
		return (
			<div
				key={c.url}
				className="border border-gray-200 rounded-lg p-3 hover:border-blue-300 hover:bg-blue-50/30 transition-all cursor-pointer"
				onClick={() => setExpandedCitation(isExpanded ? null : c.url)}
			>
				<div className="flex items-start gap-2">
					<span className="text-sm font-mono text-gray-400 shrink-0">{c.id}</span>
					<div className="flex-1 min-w-0">
						<div className="flex items-center gap-2 flex-wrap">
							<a
								href={c.url}
								target="_blank"
								rel="noopener noreferrer"
								className="text-sm font-medium text-blue-600 hover:underline truncate"
								onClick={e => e.stopPropagation()}
							>
								{c.title || 'Untitled'}
							</a>
							<span className={`px-1.5 py-0.5 text-xs rounded-full ${getSourceTypeColor(c.source_type)}`}>
								{getSourceTypeIcon(c.source_type)} {c.source_type}
							</span>
						</div>
						{c.author && (
							<p className="text-xs text-gray-500 mt-0.5">{c.author}</p>
						)}
						<div className="mt-1">
							{getRelevanceBar(c.relevance_score)}
						</div>
					</div>
				</div>
				{isExpanded && c.snippet && (
					<div className="mt-2 pl-7 text-xs text-gray-600 bg-gray-50 p-2 rounded border-l-2 border-blue-200">
						{c.snippet}
					</div>
				)}
			</div>
		);
	};

	const renderSubQueryGroup = (group: SubQueryGroup, index: number) => {
		const isExpanded = expandedGroups.has(index);
		const filteredCitations = filterType === 'all'
			? group.citations
			: group.citations.filter(c => c.source_type === filterType);

		return (
			<div key={index} className="border border-gray-200 rounded-lg overflow-hidden">
				<button
					className="w-full flex items-center gap-3 p-4 text-left hover:bg-gray-50 transition-colors"
					onClick={() => toggleGroup(index)}
				>
					<span className={`transform transition-transform ${isExpanded ? 'rotate-90' : ''}`}>
						▶
					</span>
					<div className="flex-1 min-w-0">
						<p className="text-sm font-medium text-gray-900 line-clamp-2">
							{group.sub_query}
						</p>
						<div className="flex items-center gap-3 mt-1">
							<span className="text-xs text-gray-500">
								{group.citation_count} source{group.citation_count !== 1 ? 's' : ''}
							</span>
							<span className={`text-xs px-1.5 py-0.5 rounded ${group.status === 'complete' ? 'bg-green-100 text-green-700' :
								group.status === 'failed' ? 'bg-red-100 text-red-700' :
									'bg-yellow-100 text-yellow-700'
								}`}>
								{group.status}
							</span>
						</div>
					</div>
				</button>
				{isExpanded && (
					<div className="border-t bg-gray-50/50 p-3 space-y-2">
						{group.error && (
							<div className="text-xs text-red-600 bg-red-50 p-2 rounded">
								Error: {group.error}
							</div>
						)}
						{filteredCitations.length === 0 ? (
							<p className="text-xs text-gray-400 text-center py-2">
								No sources {filterType !== 'all' ? `of type "${filterType}"` : ''}
							</p>
						) : (
							filteredCitations.map(renderCitation)
						)}
					</div>
				)}
			</div>
		);
	};

	const getAllCitations = (): KBCitation[] => {
		if (!kb) return [];
		const all: KBCitation[] = [];
		const seen = new Set<string>();
		for (const g of kb.sub_query_groups) {
			for (const c of g.citations) {
				if (!seen.has(c.url)) {
					seen.add(c.url);
					all.push(c);
				}
			}
		}
		for (const c of kb.unassigned_citations) {
			if (!seen.has(c.url)) {
				seen.add(c.url);
				all.push(c);
			}
		}
		return all;
	};

	if (loading) {
		return (
			<div className="text-center text-gray-500 py-8">
				Loading knowledge base...
			</div>
		);
	}

	if (error) {
		return (
			<div className="text-center text-red-600 py-8">
				{error}
			</div>
		);
	}

	if (!kb) return null;

	const sourceTypes = Object.keys(kb.source_type_distribution);
	const allCitations = viewMode === 'sources' ? getAllCitations() : [];
	const filteredAll = filterType === 'all'
		? allCitations
		: allCitations.filter(c => c.source_type === filterType);

	return (
		<div className="space-y-4">
			{/* Header stats */}
			<div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
				<div className="bg-blue-50 p-3 rounded-lg text-center">
					<p className="text-xl font-bold text-blue-900">{kb.total_citations}</p>
					<p className="text-xs text-blue-600">Total Sources</p>
				</div>
				<div className="bg-purple-50 p-3 rounded-lg text-center">
					<p className="text-xl font-bold text-purple-900">{kb.sub_queries.length}</p>
					<p className="text-xs text-purple-600">Sub-queries</p>
				</div>
				<div className="bg-amber-50 p-3 rounded-lg text-center">
					<p className="text-xl font-bold text-amber-900">{kb.hypotheses.length}</p>
					<p className="text-xs text-amber-600">Hypotheses</p>
				</div>
				<div className="bg-green-50 p-3 rounded-lg text-center">
					<p className="text-xl font-bold text-green-900">{sourceTypes.length}</p>
					<p className="text-xs text-green-600">Source Types</p>
				</div>
			</div>

			{/* Source type distribution */}
			{sourceTypes.length > 0 && (
				<div className="bg-white border rounded-lg p-4">
					<h3 className="text-sm font-semibold text-gray-700 mb-3">Source Distribution</h3>
					<div className="flex gap-2 flex-wrap">
						{sourceTypes.map(type => {
							const count = kb.source_type_distribution[type];
							const pct = Math.round((count / kb.total_citations) * 100);
							return (
								<button
									key={type}
									onClick={() => setFilterType(filterType === type ? 'all' : type)}
									className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm transition-all ${filterType === type
										? 'ring-2 ring-blue-400 ring-offset-1'
										: 'hover:ring-1 hover:ring-gray-300'
										} ${getSourceTypeColor(type)}`}
								>
									{getSourceTypeIcon(type)}
									<span className="font-medium">{type}</span>
									<span className="opacity-70">{count}</span>
									<span className="opacity-50">({pct}%)</span>
								</button>
							);
						})}
						{filterType !== 'all' && (
							<button
								onClick={() => setFilterType('all')}
								className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-full transition-colors"
							>
								Clear filter ✕
							</button>
						)}
					</div>
				</div>
			)}

			{/* View mode toggle */}
			<div className="flex items-center justify-between">
				<div className="flex bg-gray-100 rounded-lg p-0.5">
					<button
						onClick={() => setViewMode('tree')}
						className={`px-3 py-1.5 text-sm rounded-md transition-colors ${viewMode === 'tree'
							? 'bg-white shadow text-gray-900 font-medium'
							: 'text-gray-600 hover:text-gray-800'
							}`}
					>
						🌳 By Sub-query
					</button>
					<button
						onClick={() => setViewMode('sources')}
						className={`px-3 py-1.5 text-sm rounded-md transition-colors ${viewMode === 'sources'
							? 'bg-white shadow text-gray-900 font-medium'
							: 'text-gray-600 hover:text-gray-800'
							}`}
					>
						📋 All Sources
					</button>
				</div>
				{viewMode === 'tree' && (
					<div className="flex gap-2">
						<button
							onClick={expandAll}
							className="text-xs text-blue-600 hover:text-blue-800"
						>
							Expand all
						</button>
						<span className="text-gray-300">|</span>
						<button
							onClick={collapseAll}
							className="text-xs text-blue-600 hover:text-blue-800"
						>
							Collapse all
						</button>
					</div>
				)}
			</div>

			{/* Tree view: sub-query groups */}
			{viewMode === 'tree' && (
				<div className="space-y-3">
					{/* Main query header */}
					<div className="bg-gradient-to-r from-blue-50 to-purple-50 border border-blue-200 rounded-lg p-4">
						<p className="text-xs text-blue-500 font-medium uppercase tracking-wide">Research Query</p>
						<p className="text-lg font-semibold text-gray-900 mt-1">{kb.query}</p>
					</div>

					{/* Sub-query groups */}
					{kb.sub_query_groups.map((group, i) => renderSubQueryGroup(group, i))}

					{/* Hypothesis-sourced citations */}
					{kb.hypotheses.length > 0 && (
						<div className="border border-amber-200 rounded-lg overflow-hidden">
							<div className="bg-amber-50 px-4 py-3 border-b border-amber-200">
								<p className="text-sm font-medium text-amber-800">
									💡 Hypothesis Investigations ({kb.hypotheses.length})
								</p>
								<p className="text-xs text-amber-600 mt-0.5">
									Additional sources found through hypothesis-driven exploration
								</p>
							</div>
							<div className="p-3 space-y-2">
								{kb.hypotheses.map((h, i) => (
									<div key={i} className="bg-white border border-amber-100 rounded-lg p-3">
										<div className="flex items-start gap-2">
											<span className={`text-xs px-1.5 py-0.5 rounded ${h.status === 'completed' ? 'bg-green-100 text-green-700' :
												h.status === 'error' ? 'bg-red-100 text-red-700' :
													'bg-gray-100 text-gray-700'
												}`}>
												{h.status}
											</span>
											<div>
												<p className="text-sm font-medium text-gray-800">{h.title}</p>
												<p className="text-xs text-gray-500 mt-0.5">{h.description}</p>
												{h.metadata.sources_found !== undefined && (
													<p className="text-xs text-amber-600 mt-1">
														Found {h.metadata.sources_found as number} new source{(h.metadata.sources_found as number) !== 1 ? 's' : ''}
													</p>
												)}
											</div>
										</div>
									</div>
								))}
							</div>
						</div>
					)}

					{/* Unassigned citations */}
					{kb.unassigned_citations.length > 0 && (
						<div className="border border-gray-200 rounded-lg overflow-hidden">
							<div className="bg-gray-50 px-4 py-3 border-b">
								<p className="text-sm font-medium text-gray-700">
									Additional Sources ({kb.unassigned_citations.length})
								</p>
								<p className="text-xs text-gray-500 mt-0.5">
									Sources discovered during hypothesis exploration
								</p>
							</div>
							<div className="p-3 space-y-2">
								{kb.unassigned_citations
									.filter(c => filterType === 'all' || c.source_type === filterType)
									.map(renderCitation)}
							</div>
						</div>
					)}
				</div>
			)}

			{/* Flat sources view */}
			{viewMode === 'sources' && (
				<div className="space-y-2">
					<p className="text-sm text-gray-500">
						{filteredAll.length} source{filteredAll.length !== 1 ? 's' : ''}
						{filterType !== 'all' && ` (filtered: ${filterType})`}
					</p>
					{filteredAll.length === 0 ? (
						<p className="text-center text-gray-400 py-8">No sources found</p>
					) : (
						filteredAll.map(renderCitation)
					)}
				</div>
			)}
		</div>
	);
}
