import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { Research, Source, Finding } from '../types';
import ProgressMonitor from './ProgressMonitor';
import ChatInterface from './ChatInterface';

interface Props {
	researchId: number;
	onDelete: (id: number) => void;
	onUpdate: () => void;
}

type Tab = 'overview' | 'sources' | 'findings' | 'progress' | 'chat';

export default function ResearchDetail({ researchId, onDelete, onUpdate }: Props) {
	const [research, setResearch] = useState<Research | null>(null);
	const [sources, setSources] = useState<Source[]>([]);
	const [findings, setFindings] = useState<Finding[]>([]);
	const [activeTab, setActiveTab] = useState<Tab>('overview');
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		loadData();
	}, [researchId]);

	const loadData = async () => {
		try {
			setLoading(true);
			setError(null);
			const [researchData, sourcesData, findingsData] = await Promise.all([
				api.getResearch(researchId),
				api.getSources(researchId),
				api.getFindings(researchId),
			]);
			setResearch(researchData);
			setSources(sourcesData);
			setFindings(findingsData);
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Failed to load research');
		} finally {
			setLoading(false);
		}
	};

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
		{ id: 'progress', label: 'Progress' },
		{ id: 'chat', label: 'Chat' },
	];

	return (
		<div className="bg-white rounded-lg shadow">
			{/* Header */}
			<div className="p-6 border-b">
				<div className="flex items-start justify-between">
					<div className="flex-1">
						<h2 className="text-xl font-semibold text-gray-900">
							{research.query}
						</h2>
						<div className="flex items-center gap-2 mt-2">
							<span
								className={`px-2 py-1 text-xs rounded-full ${research.status === 'completed'
										? 'bg-green-100 text-green-700'
										: research.status === 'researching'
											? 'bg-blue-100 text-blue-700'
											: research.status === 'failed'
												? 'bg-red-100 text-red-700'
												: 'bg-gray-100 text-gray-700'
									}`}
							>
								{research.status}
							</span>
							<span className="text-sm text-gray-500">
								Created {new Date(research.created_at).toLocaleString()}
							</span>
						</div>
					</div>

					<div className="flex gap-2">
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
					<div className="space-y-3">
						{sources.length === 0 ? (
							<p className="text-center text-gray-500 py-8">No sources yet</p>
						) : (
							sources.map((source) => (
								<div key={source.id} className="border rounded-lg p-4 hover:bg-gray-50">
									<a
										href={source.url}
										target="_blank"
										rel="noopener noreferrer"
										className="text-blue-600 hover:underline font-medium"
									>
										{source.title}
									</a>
									<div className="flex items-center gap-2 mt-2 text-xs text-gray-500">
										<span className="px-2 py-1 bg-gray-100 rounded">
											{source.source_type}
										</span>
										<span>{new Date(source.created_at).toLocaleString()}</span>
									</div>
									{source.content && (
										<p className="mt-2 text-sm text-gray-600 line-clamp-3">
											{source.content}
										</p>
									)}
								</div>
							))
						)}
					</div>
				)}

				{activeTab === 'findings' && (
					<div className="space-y-3">
						{findings.length === 0 ? (
							<p className="text-center text-gray-500 py-8">No findings yet</p>
						) : (
							findings.map((finding) => (
								<div key={finding.id} className="border rounded-lg p-4">
									<p className="text-sm text-gray-900">{finding.content}</p>
									{finding.category && (
										<span className="inline-block mt-2 px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded">
											{finding.category}
										</span>
									)}
									{finding.user_notes && (
										<p className="mt-2 text-xs text-gray-600 italic">
											Note: {finding.user_notes}
										</p>
									)}
								</div>
							))
						)}
					</div>
				)}

				{activeTab === 'progress' && <ProgressMonitor researchId={researchId} />}

				{activeTab === 'chat' && <ChatInterface researchId={researchId} />}
			</div>
		</div>
	);
}
