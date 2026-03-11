import { useState, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import { api } from '../api/client';
import type { Research, Source, Finding, AgentStep } from '../types';
import ChatInterface from './ChatInterface';
import EditableResearchHeader from './EditableResearchHeader';
import AgentSteps from './AgentSteps';
import KnowledgeBase from './KnowledgeBase';
import ResearchNotes from './ResearchNotes';
import SourceFormModal from './SourceFormModal';
import FindingFormModal from './FindingFormModal';
import ConfirmDialog from './ConfirmDialog';
import SourcesFilterBar, { type SourceFilters } from './SourcesFilterBar';
import FindingsFilterBar, { type FindingFilters } from './FindingsFilterBar';
import ExportMenu from './ExportMenu';

interface Props {
	researchId: number;
	onDelete: (id: number) => void;
	onUpdate: () => void;
}

type Tab = 'overview' | 'sources' | 'findings' | 'result' | 'knowledge' | 'notes' | 'chat' | 'steps';

export default function ResearchDetail({ researchId, onDelete, onUpdate }: Props) {
	const [research, setResearch] = useState<Research | null>(null);
	const [sources, setSources] = useState<Source[]>([]);
	const [findings, setFindings] = useState<Finding[]>([]);
	const [activeTab, setActiveTab] = useState<Tab>('overview');
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [latestStep, setLatestStep] = useState<AgentStep | null>(null);

	// Source filtering state
	const [sourceFilters, setSourceFilters] = useState<SourceFilters>({
		sort_by: undefined,
		sort_order: 'desc',
	});
	const [allSources, setAllSources] = useState<Source[]>([]); // Store all sources for quick filters
	const [filteredSources, setFilteredSources] = useState<Source[]>([]);

	// Finding filtering state
	const [findingFilters, setFindingFilters] = useState<FindingFilters>({
		sort_order: 'desc',
	});
	const [filteredFindings, setFilteredFindings] = useState<Finding[]>([]);

	// Source CRUD state
	const [sourceModalOpen, setSourceModalOpen] = useState(false);
	const [editingSource, setEditingSource] = useState<Source | null>(null);
	const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
	const [sourceToDelete, setSourceToDelete] = useState<number | null>(null);
	const [editingNotes, setEditingNotes] = useState<{ [key: number]: string }>({});

	// Finding CRUD state
	const [findingModalOpen, setFindingModalOpen] = useState(false);
	const [editingFinding, setEditingFinding] = useState<Finding | null>(null);
	const [findingDeleteConfirmOpen, setFindingDeleteConfirmOpen] = useState(false);
	const [findingToDelete, setFindingToDelete] = useState<number | null>(null);
	const [editingFindingContent, setEditingFindingContent] = useState<{ [key: number]: string }>({});

	const loadSources = useCallback(async (filters?: SourceFilters) => {
		try {
			// Build filter params for API
			const apiFilters: any = {};
			if (filters?.source_type) apiFilters.source_type = filters.source_type;
			if (filters?.search) apiFilters.search = filters.search;
			if (filters?.sort_by) {
				apiFilters.sort_by = filters.sort_by;
				apiFilters.sort_order = filters.sort_order || 'desc';
			}

			const sourcesData = await api.getSources(researchId, apiFilters);
			setAllSources(sourcesData);

			// Apply quick filters on frontend (since they're complex logic)
			let filtered = sourcesData;
			if (filters?.quick_filter) {
				const now = Date.now();
				const oneDayMs = 24 * 60 * 60 * 1000;

				switch (filters.quick_filter) {
					case 'academic':
						filtered = filtered.filter(s =>
							['arxiv', 'pubmed', 'semantic_scholar', 'openalex', 'crossref'].includes(s.source_type)
						);
						break;
					case 'recent':
						filtered = filtered.filter(s =>
							now - new Date(s.accessed_at).getTime() < oneDayMs
						);
						break;
					case 'no_content':
						filtered = filtered.filter(s => !s.content_snippet || s.content_snippet.trim().length === 0);
						break;
				}
			}

			setFilteredSources(filtered);
			setSources(filtered);
		} catch (err) {
			console.error('Failed to load sources:', err);
		}
	}, [researchId]);

	const loadFindings = useCallback(async (filters?: FindingFilters) => {
		try {
			// Build filter params for API
			const apiFilters: any = {};
			if (filters?.source_id) apiFilters.source_id = filters.source_id;
			if (filters?.search) apiFilters.search = filters.search;
			if (filters?.sort_order) {
				apiFilters.sort_by = 'created_at';
				apiFilters.sort_order = filters.sort_order;
			}

			const findingsData = await api.getFindings(researchId, apiFilters);
			setFilteredFindings(findingsData);
			setFindings(findingsData);
		} catch (err) {
			console.error('Failed to load findings:', err);
		}
	}, [researchId]);

	const loadData = useCallback(async () => {
		try {
			setLoading(true);
			setError(null);
			const researchData = await api.getResearch(researchId);
			await Promise.all([
				loadSources(sourceFilters),
				loadFindings(findingFilters),
			]);
			setResearch(researchData);
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Failed to load research');
		} finally {
			setLoading(false);
		}
	}, [researchId, loadSources, loadFindings, sourceFilters, findingFilters]);

	useEffect(() => {
		loadData();
	}, [loadData]);

	useEffect(() => {
		if (!research || research.status !== 'researching') return;

		const pollProgress = async () => {
			try {
				const [researchData, stepsData] = await Promise.all([
					api.getResearch(researchId),
					api.getAgentSteps(researchId),
				]);
				if (stepsData.steps.length > 0) {
					setLatestStep(stepsData.steps[stepsData.steps.length - 1]);
				}
				if (researchData.status !== 'researching') {
					setLatestStep(null);
					loadData();
				} else {
					setResearch(researchData);
				}
			} catch {
				// silent fail — polling will retry
			}
		};

		const interval = setInterval(pollProgress, 1000);
		return () => clearInterval(interval);
	}, [research, researchId, loadData]);

	const handleDelete = async () => {
		if (!confirm('Are you sure you want to delete this research?')) return;

		try {
			await api.deleteResearch(researchId);
			onDelete(researchId);
		} catch (err) {
			alert(err instanceof Error ? err.message : 'Failed to delete research');
		}
	};

	const handleCancel = async () => {
		try {
			await api.cancelResearch(researchId);
			onUpdate();
			loadData();
		} catch (err) {
			alert(err instanceof Error ? err.message : 'Failed to cancel research');
		}
	};

	const handleResume = async () => {
		try {
			await api.resumeResearch(researchId);
			onUpdate();
			loadData();
		} catch (err) {
			alert(err instanceof Error ? err.message : 'Failed to resume research');
		}
	};

	const handleUpdateQuery = async (query: string) => {
		try {
			const updatedResearch = await api.updateResearch(researchId, { query });
			setResearch(updatedResearch);
			onUpdate();
		} catch (err) {
			throw err;
		}
	};

	// Source filter handler
	const handleSourceFiltersChange = (filters: SourceFilters) => {
		setSourceFilters(filters);
		loadSources(filters);
	};

	// Finding filter handler
	const handleFindingFiltersChange = (filters: FindingFilters) => {
		setFindingFilters(filters);
		loadFindings(filters);
	};

	// Source CRUD handlers
	const handleAddSource = () => {
		setEditingSource(null);
		setSourceModalOpen(true);
	};

	const handleEditSource = (source: Source) => {
		setEditingSource(source);
		setSourceModalOpen(true);
	};

	const handleSourceModalSubmit = async (sourceData: any) => {
		try {
			if (editingSource) {
				// Update existing source
				const updated = await api.updateSource(researchId, editingSource.id, {
					user_notes: sourceData.user_notes,
					tags: sourceData.tags,
					title: sourceData.title,
				});
				setSources((prev) =>
					prev.map((s) => (s.id === updated.id ? updated : s))
				);
			} else {
				// Create new source
				const newSource = await api.createSource(researchId, sourceData);
				setSources((prev) => [newSource, ...prev]);
			}
			setSourceModalOpen(false);
			setEditingSource(null);
		} catch (err) {
			throw err;
		}
	};

	const handleDeleteSource = (sourceId: number) => {
		setSourceToDelete(sourceId);
		setDeleteConfirmOpen(true);
	};

	const handleConfirmDelete = async () => {
		if (sourceToDelete === null) return;

		try {
			await api.deleteSource(researchId, sourceToDelete);
			setSources((prev) => prev.filter((s) => s.id !== sourceToDelete));
			setDeleteConfirmOpen(false);
			setSourceToDelete(null);
		} catch (err) {
			alert(err instanceof Error ? err.message : 'Failed to delete source');
			setDeleteConfirmOpen(false);
			setSourceToDelete(null);
		}
	};

	const handleStartEditNotes = (sourceId: number, currentNotes: string) => {
		setEditingNotes((prev) => ({ ...prev, [sourceId]: currentNotes || '' }));
	};

	const handleCancelEditNotes = (sourceId: number) => {
		setEditingNotes((prev) => {
			const updated = { ...prev };
			delete updated[sourceId];
			return updated;
		});
	};

	const handleSaveNotes = async (sourceId: number) => {
		const notes = editingNotes[sourceId];
		try {
			const updated = await api.updateSource(researchId, sourceId, {
				user_notes: notes,
			});
			setSources((prev) =>
				prev.map((s) => (s.id === updated.id ? updated : s))
			);
			handleCancelEditNotes(sourceId);
		} catch (err) {
			alert(err instanceof Error ? err.message : 'Failed to update notes');
		}
	};

	// Finding CRUD handlers
	const handleAddFinding = () => {
		setEditingFinding(null);
		setFindingModalOpen(true);
	};

	const handleEditFinding = (finding: Finding) => {
		setEditingFinding(finding);
		setFindingModalOpen(true);
	};

	const handleFindingModalSubmit = async (findingData: { content: string; source_ids?: number[] }) => {
		try {
			if (editingFinding) {
				// Update existing finding
				const updated = await api.updateFinding(researchId, editingFinding.id, findingData);
				setFindings((prev) =>
					prev.map((f) => (f.id === updated.id ? updated : f))
				);
			} else {
				// Create new finding
				const newFinding = await api.createFinding(researchId, findingData);
				setFindings((prev) => [newFinding, ...prev]);
			}
			setFindingModalOpen(false);
			setEditingFinding(null);
		} catch (err) {
			throw err;
		}
	};

	const handleDeleteFinding = (findingId: number) => {
		setFindingToDelete(findingId);
		setFindingDeleteConfirmOpen(true);
	};

	const handleConfirmDeleteFinding = async () => {
		if (findingToDelete === null) return;

		try {
			await api.deleteFinding(researchId, findingToDelete);
			setFindings((prev) => prev.filter((f) => f.id !== findingToDelete));
			setFindingDeleteConfirmOpen(false);
			setFindingToDelete(null);
		} catch (err) {
			alert(err instanceof Error ? err.message : 'Failed to delete finding');
			setFindingDeleteConfirmOpen(false);
			setFindingToDelete(null);
		}
	};

	const handleStartEditFindingContent = (findingId: number, currentContent: string) => {
		setEditingFindingContent((prev) => ({ ...prev, [findingId]: currentContent }));
	};

	const handleCancelEditFindingContent = (findingId: number) => {
		setEditingFindingContent((prev) => {
			const updated = { ...prev };
			delete updated[findingId];
			return updated;
		});
	};

	const handleSaveFindingContent = async (findingId: number) => {
		const content = editingFindingContent[findingId];
		if (!content.trim()) {
			alert('Content cannot be empty');
			return;
		}
		try {
			const updated = await api.updateFinding(researchId, findingId, {
				content: content.trim(),
			});
			setFindings((prev) =>
				prev.map((f) => (f.id === updated.id ? updated : f))
			);
			handleCancelEditFindingContent(findingId);
		} catch (err) {
			alert(err instanceof Error ? err.message : 'Failed to update finding');
		}
	};

	if (loading) {
		return (
			<div className="bg-white rounded-lg shadow p-12 text-center">
				<p className="text-gray-500">Loading...</p>
			</div>
		);
	}

	if (error || !research) {
		return (
			<div className="bg-white rounded-lg shadow p-12 text-center">
				<p className="text-red-600">{error || 'Research not found'}</p>
			</div>
		);
	}

	const tabs: { id: Tab; label: string; count?: number }[] = [
		{ id: 'overview', label: 'Overview' },
		{ id: 'sources', label: 'Sources', count: sources.length },
		{ id: 'findings', label: 'Findings', count: findings.length },
		{ id: 'result', label: 'Result' },
		{ id: 'knowledge', label: 'Knowledge Base' },
		{ id: 'notes', label: 'Notes' },
		{ id: 'steps', label: 'Agent Steps' },
		{ id: 'chat', label: 'Chat' },
	];

	return (
		<div className="bg-white rounded-lg shadow">
			{/* Header */}
			<div className="p-6 border-b">
				<div className="flex items-start justify-between">
					<EditableResearchHeader
						research={research}
						onUpdate={setResearch}
						onUpdateQuery={handleUpdateQuery}
					/>

					<div className="flex gap-2">
						{['error', 'failed', 'cancelled'].includes(research.status) && (
							<button
								onClick={handleResume}
								className="px-3 py-1 text-sm text-blue-600 hover:bg-blue-50 rounded transition-colors"
							>
								Resume
							</button>
						)}
						{research.status === 'researching' && (
							<button
								onClick={handleCancel}
								className="px-3 py-1 text-sm text-orange-600 hover:bg-orange-50 rounded transition-colors"
							>
								Cancel
							</button>
						)}
						<button
							onClick={handleDelete}
							className="px-3 py-1 text-sm text-red-600 hover:bg-red-50 rounded transition-colors"
						>
							Delete
						</button>
					</div>
				</div>

				{research.user_notes && (
					<p className="mt-3 text-sm text-gray-600 bg-gray-50 p-3 rounded">
						{research.user_notes}
					</p>
				)}
			</div>

			{/* Tabs */}
			<div className="border-b">
				<nav className="flex gap-1 px-6">
					{tabs.map((tab) => (
						<button
							key={tab.id}
							onClick={() => setActiveTab(tab.id)}
							className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${activeTab === tab.id
								? 'border-blue-600 text-blue-600'
								: 'border-transparent text-gray-600 hover:text-gray-900'
								}`}
						>
							{tab.label}
							{tab.count !== undefined && (
								<span className="ml-2 text-xs text-gray-500">({tab.count})</span>
							)}
						</button>
					))}
				</nav>
			</div>

			{/* Tab Content */}
			<div className="p-6">
				{activeTab === 'overview' && (
					<div className="space-y-4">
						{research.status === 'researching' && (
							<div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
								<div className="flex items-center gap-2">
									<span className="w-2.5 h-2.5 rounded-full bg-blue-500 animate-pulse flex-shrink-0" />
									<h3 className="text-sm font-semibold text-blue-800">Research in progress</h3>
								</div>
								{latestStep ? (
									<div className="mt-3 pl-5">
										<p className="text-xs font-medium text-blue-600 uppercase tracking-wider">
											{latestStep.step_type.replace(/_/g, ' ')}
										</p>
										<p className="text-sm font-medium text-blue-900 mt-0.5">{latestStep.title}</p>
										{latestStep.description && (
											<p className="text-sm text-blue-700 mt-1">{latestStep.description}</p>
										)}
									</div>
								) : (
									<p className="mt-2 pl-5 text-sm text-blue-700">Starting…</p>
								)}
							</div>
						)}
						{['error', 'failed', 'cancelled'].includes(research.status) && (
							<div className="bg-red-50 border border-red-200 rounded-lg p-4">
								<div className="flex items-center justify-between">
									<div className="flex items-center gap-2">
										<span className="text-red-500 flex-shrink-0">✕</span>
										<h3 className="text-sm font-semibold text-red-800">
											{research.status === 'cancelled' ? 'Research was cancelled' : 'Research encountered an error'}
										</h3>
									</div>
									<button
										onClick={handleResume}
										className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded transition-colors"
									>
										Resume
									</button>
								</div>
								<p className="mt-2 pl-6 text-sm text-red-700">
									Progress has been saved. Click Resume to continue from where it left off.
								</p>
							</div>
						)}
						<div className="grid grid-cols-3 gap-4">
							<div className="bg-blue-50 p-4 rounded-lg">
								<p className="text-sm text-blue-600 font-medium">Sources</p>
								<p className="text-2xl font-bold text-blue-900">{sources.length}</p>
							</div>
							<div className="bg-green-50 p-4 rounded-lg">
								<p className="text-sm text-green-600 font-medium">Findings</p>
								<p className="text-2xl font-bold text-green-900">{findings.length}</p>
							</div>
							<div className="bg-purple-50 p-4 rounded-lg">
								<p className="text-sm text-purple-600 font-medium">Status</p>
								<p className="text-lg font-bold text-purple-900 capitalize">
									{research.status}
								</p>
							</div>
						</div>

						{sources.length > 0 && (
							<div>
								<h3 className="text-sm font-semibold text-gray-700 mb-2">
									Recent Sources
								</h3>
								<div className="space-y-2">
									{sources.slice(0, 3).map((source) => (
										<div key={source.id} className="p-3 bg-gray-50 rounded">
											<a
												href={source.url}
												target="_blank"
												rel="noopener noreferrer"
												className="text-sm font-medium text-blue-600 hover:underline"
											>
												{source.title}
											</a>
											<p className="text-xs text-gray-500 mt-1">{source.source_type}</p>
										</div>
									))}
								</div>
							</div>
						)}
					</div>
				)}

				{activeTab === 'sources' && (
					<div>
						<div className="flex justify-between items-center mb-4">
							<h3 className="text-lg font-semibold text-gray-900">
								Sources
							</h3>
							<div className="flex gap-2">
								<ExportMenu researchId={researchId} type="sources" />
								<button
									onClick={handleAddSource}
									className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700 transition-colors"
								>
									+ Add Source
								</button>
							</div>
						</div>

						<SourcesFilterBar
							filters={sourceFilters}
							onFiltersChange={handleSourceFiltersChange}
							totalSources={filteredSources.length}
						/>

						<div className="space-y-3">
							{sources.length === 0 ? (
								<div className="text-center py-12">
									<p className="text-gray-500 mb-4">No sources yet</p>
									<button
										onClick={handleAddSource}
										className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700 transition-colors"
									>
										Add your first source
									</button>
								</div>
							) : (
								sources.map((source) => {
									const isEditingNotes = editingNotes[source.id] !== undefined;
									return (
										<div key={source.id} className="border rounded-lg p-4 hover:bg-gray-50">
											<div className="flex items-start justify-between">
												<div className="flex-1 min-w-0">
													<a
														href={source.url}
														target="_blank"
														rel="noopener noreferrer"
														className="text-blue-600 hover:underline font-medium break-words"
													>
														{source.title}
													</a>
													<div className="flex items-center gap-2 mt-2 text-xs text-gray-500 flex-wrap">
														<span className="px-2 py-1 bg-gray-100 rounded">
															{source.source_type}
														</span>
														<span>{new Date(source.accessed_at).toLocaleString()}</span>
														{source.author && (
															<span className="text-gray-600">by {source.author}</span>
														)}
													</div>
													{source.content_snippet && (
														<p className="mt-2 text-sm text-gray-600 line-clamp-3">
															{source.content_snippet}
														</p>
													)}
													{source.tags && source.tags.length > 0 && (
														<div className="flex gap-1 mt-2 flex-wrap">
															{source.tags.map((tag) => (
																<span
																	key={tag}
																	className="px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded"
																>
																	{tag}
																</span>
															))}
														</div>
													)}

													{/* Notes section with inline editing */}
													<div className="mt-3">
														{isEditingNotes ? (
															<div className="space-y-2">
																<textarea
																	value={editingNotes[source.id]}
																	onChange={(e) =>
																		setEditingNotes((prev) => ({
																			...prev,
																			[source.id]: e.target.value,
																		}))
																	}
																	className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
																	rows={3}
																	placeholder="Add notes about this source..."
																/>
																<div className="flex gap-2">
																	<button
																		onClick={() => handleSaveNotes(source.id)}
																		className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
																	>
																		Save
																	</button>
																	<button
																		onClick={() => handleCancelEditNotes(source.id)}
																		className="px-3 py-1 border border-gray-300 text-gray-700 text-sm rounded hover:bg-gray-50 transition-colors"
																	>
																		Cancel
																	</button>
																</div>
															</div>
														) : (
															<>
																{source.user_notes ? (
																	<div className="bg-yellow-50 border border-yellow-200 rounded p-2">
																		<p className="text-sm text-gray-700">{source.user_notes}</p>
																	</div>
																) : (
																	<p className="text-sm text-gray-400 italic">No notes</p>
																)}
															</>
														)}
													</div>
												</div>

												<div className="ml-3 flex gap-1 flex-shrink-0">
													{!isEditingNotes && (
														<button
															onClick={() =>
																handleStartEditNotes(source.id, source.user_notes || '')
															}
															className="p-2 text-gray-600 hover:bg-gray-100 rounded transition-colors"
															title="Edit notes"
														>
															<svg
																className="w-4 h-4"
																fill="none"
																stroke="currentColor"
																viewBox="0 0 24 24"
															>
																<path
																	strokeLinecap="round"
																	strokeLinejoin="round"
																	strokeWidth={2}
																	d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
																/>
															</svg>
														</button>
													)}
													<button
														onClick={() => handleEditSource(source)}
														className="p-2 text-blue-600 hover:bg-blue-50 rounded transition-colors"
														title="Edit source"
													>
														<svg
															className="w-4 h-4"
															fill="none"
															stroke="currentColor"
															viewBox="0 0 24 24"
														>
															<path
																strokeLinecap="round"
																strokeLinejoin="round"
																strokeWidth={2}
																d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
															/>
														</svg>
													</button>
													<button
														onClick={() => handleDeleteSource(source.id)}
														className="p-2 text-red-600 hover:bg-red-50 rounded transition-colors"
														title="Delete source"
													>
														<svg
															className="w-4 h-4"
															fill="none"
															stroke="currentColor"
															viewBox="0 0 24 24"
														>
															<path
																strokeLinecap="round"
																strokeLinejoin="round"
																strokeWidth={2}
																d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
															/>
														</svg>
													</button>
												</div>
											</div>
										</div>
									);
								})
							)}
						</div>
					</div>
				)}

				{activeTab === 'findings' && (
					<div>
						<div className="flex justify-between items-center mb-4">
							<h3 className="text-lg font-semibold text-gray-900">
								Findings
							</h3>
							<div className="flex gap-2">
								<ExportMenu researchId={researchId} type="findings" />
								<button
									onClick={handleAddFinding}
									className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700 transition-colors"
								>
									+ Add Finding
								</button>
							</div>
						</div>

						<FindingsFilterBar
							filters={findingFilters}
							onFiltersChange={handleFindingFiltersChange}
							totalFindings={filteredFindings.length}
							sources={allSources}
						/>

						<div className="space-y-3">
							{findings.length === 0 ? (
								<div className="text-center py-12">
									<p className="text-gray-500 mb-4">No findings yet</p>
									<button
										onClick={handleAddFinding}
										className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700 transition-colors"
									>
										Add your first finding
									</button>
								</div>
							) : (
								findings.map((finding) => {
									const isEditingContent = editingFindingContent[finding.id] !== undefined;
									return (
										<div key={finding.id} className="border rounded-lg p-4 hover:bg-gray-50">
											<div className="flex items-start justify-between">
												<div className="flex-1 min-w-0">
													{isEditingContent ? (
														<div className="space-y-2">
															<textarea
																value={editingFindingContent[finding.id]}
																onChange={(e) =>
																	setEditingFindingContent((prev) => ({
																		...prev,
																		[finding.id]: e.target.value,
																	}))
																}
																className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
																rows={4}
																placeholder="Finding content..."
															/>
															<div className="flex gap-2">
																<button
																	onClick={() => handleSaveFindingContent(finding.id)}
																	className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
																>
																	Save
																</button>
																<button
																	onClick={() => handleCancelEditFindingContent(finding.id)}
																	className="px-3 py-1 border border-gray-300 text-gray-700 text-sm rounded hover:bg-gray-50 transition-colors"
																>
																	Cancel
																</button>
															</div>
														</div>
													) : (
														<>
															<p className="text-sm text-gray-900 whitespace-pre-wrap">
																{finding.content}
															</p>
															{finding.category && (
																<span className="inline-block mt-2 px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded">
																	{finding.category}
																</span>
															)}
															{finding.user_notes && (
																<p className="mt-2 text-xs text-gray-600 italic bg-yellow-50 border border-yellow-200 rounded p-2">
																	Note: {finding.user_notes}
																</p>
															)}
															{finding.source_ids && finding.source_ids.length > 0 && (
																<div className="mt-2">
																	<p className="text-xs text-gray-500">
																		Linked to {finding.source_ids.length} source
																		{finding.source_ids.length !== 1 ? 's' : ''}
																	</p>
																</div>
															)}
															<div className="flex items-center gap-2 mt-2 text-xs text-gray-500">
																{finding.created_by && (
																	<span className="px-2 py-0.5 bg-gray-100 rounded">
																		by {finding.created_by}
																	</span>
																)}
																<span>{new Date(finding.created_at).toLocaleString()}</span>
															</div>
														</>
													)}
												</div>

												<div className="ml-3 flex gap-1 flex-shrink-0">
													{!isEditingContent && (
														<>
															<button
																onClick={() =>
																	handleStartEditFindingContent(finding.id, finding.content)
																}
																className="p-2 text-gray-600 hover:bg-gray-100 rounded transition-colors"
																title="Edit content"
															>
																<svg
																	className="w-4 h-4"
																	fill="none"
																	stroke="currentColor"
																	viewBox="0 0 24 24"
																>
																	<path
																		strokeLinecap="round"
																		strokeLinejoin="round"
																		strokeWidth={2}
																		d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
																	/>
																</svg>
															</button>
															<button
																onClick={() => handleEditFinding(finding)}
																className="p-2 text-blue-600 hover:bg-blue-50 rounded transition-colors"
																title="Edit finding and sources"
															>
																<svg
																	className="w-4 h-4"
																	fill="none"
																	stroke="currentColor"
																	viewBox="0 0 24 24"
																>
																	<path
																		strokeLinecap="round"
																		strokeLinejoin="round"
																		strokeWidth={2}
																		d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
																	/>
																</svg>
															</button>
															<button
																onClick={() => handleDeleteFinding(finding.id)}
																className="p-2 text-red-600 hover:bg-red-50 rounded transition-colors"
																title="Delete finding"
															>
																<svg
																	className="w-4 h-4"
																	fill="none"
																	stroke="currentColor"
																	viewBox="0 0 24 24"
																>
																	<path
																		strokeLinecap="round"
																		strokeLinejoin="round"
																		strokeWidth={2}
																		d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
																	/>
																</svg>
															</button>
														</>
													)}
												</div>
											</div>
										</div>
									);
								})
							)}
						</div>
					</div>
				)}

				{activeTab === 'result' && (
					<div>
						{!research.result ? (
							<div className="text-center text-gray-500 py-8">
								<p>No research report available yet.</p>
								{research.status === 'researching' && (
									<p className="mt-2 text-sm">The report will be generated once research is complete.</p>
								)}
							</div>
						) : (
							<div className="prose prose-sm max-w-none prose-headings:text-gray-900 prose-p:text-gray-700 prose-a:text-blue-600 prose-code:text-pink-600 prose-pre:bg-gray-50">
								<ReactMarkdown>{research.result}</ReactMarkdown>
							</div>
						)}
					</div>
				)}

				{activeTab === 'knowledge' && <KnowledgeBase researchId={researchId} />}

				{activeTab === 'notes' && <ResearchNotes researchId={researchId} />}

				{activeTab === 'steps' && <AgentSteps researchId={researchId} />}

				{activeTab === 'chat' && <ChatInterface researchId={researchId} />}
			</div>

			{/* Modals */}
			<SourceFormModal
				isOpen={sourceModalOpen}
				source={editingSource}
				onClose={() => {
					setSourceModalOpen(false);
					setEditingSource(null);
				}}
				onSubmit={handleSourceModalSubmit}
			/>

			<FindingFormModal
				isOpen={findingModalOpen}
				finding={editingFinding}
				sources={sources}
				onClose={() => {
					setFindingModalOpen(false);
					setEditingFinding(null);
				}}
				onSubmit={handleFindingModalSubmit}
			/>

			<ConfirmDialog
				isOpen={deleteConfirmOpen}
				title="Delete Source"
				message="Are you sure you want to delete this source? This action cannot be undone."
				confirmLabel="Delete"
				cancelLabel="Cancel"
				confirmStyle="danger"
				onConfirm={handleConfirmDelete}
				onCancel={() => {
					setDeleteConfirmOpen(false);
					setSourceToDelete(null);
				}}
			/>

			<ConfirmDialog
				isOpen={findingDeleteConfirmOpen}
				title="Delete Finding"
				message="Are you sure you want to delete this finding? This action cannot be undone."
				confirmLabel="Delete"
				cancelLabel="Cancel"
				confirmStyle="danger"
				onConfirm={handleConfirmDeleteFinding}
				onCancel={() => {
					setFindingDeleteConfirmOpen(false);
					setFindingToDelete(null);
				}}
			/>
		</div>
	);
}
