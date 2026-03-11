import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import type { ResearchState } from '../types';

interface Props {
	researchId: number;
}

export default function StateInspector({ researchId }: Props) {
	const [expanded, setExpanded] = useState(false);
	const [state, setState] = useState<ResearchState | null>(null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const loadState = useCallback(async () => {
		try {
			setLoading(true);
			setError(null);
			const data = await api.getState(researchId);
			setState(data);
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Failed to load AI state');
		} finally {
			setLoading(false);
		}
	}, [researchId]);

	useEffect(() => {
		if (!expanded) return;
		loadState();
	}, [expanded, loadState]);

	return (
		<div className="border border-gray-200 rounded-lg">
			<button
				onClick={() => setExpanded((v) => !v)}
				className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 transition-colors"
			>
				<div>
					<p className="text-sm font-semibold text-gray-900">AI State Inspector</p>
					<p className="text-xs text-gray-500">See progress, pending/completed queries, and reasoning history</p>
				</div>
				<span className="text-sm text-gray-500">{expanded ? 'Hide' : 'Show'}</span>
			</button>

			{expanded && (
				<div className="border-t border-gray-200 p-4 space-y-4">
					{loading && <p className="text-sm text-gray-500">Loading state...</p>}
					{error && <p className="text-sm text-red-600">{error}</p>}

					{!loading && !error && state && (
						<>
							<div className="grid grid-cols-2 md:grid-cols-4 gap-3">
								<div className="bg-gray-50 rounded p-3">
									<p className="text-xs text-gray-500">Status</p>
									<p className="text-sm font-medium text-gray-900 capitalize">{state.status || 'unknown'}</p>
								</div>
								<div className="bg-gray-50 rounded p-3">
									<p className="text-xs text-gray-500">Sources</p>
									<p className="text-sm font-medium text-gray-900">{state.source_count ?? 0}</p>
								</div>
								<div className="bg-gray-50 rounded p-3">
									<p className="text-xs text-gray-500">Findings</p>
									<p className="text-sm font-medium text-gray-900">{state.finding_count ?? 0}</p>
								</div>
								<div className="bg-gray-50 rounded p-3">
									<p className="text-xs text-gray-500">Last Activity</p>
									<p className="text-sm font-medium text-gray-900">
										{state.last_activity
											? new Date(state.last_activity).toLocaleString()
											: 'N/A'}
									</p>
								</div>
							</div>

							<div className="grid md:grid-cols-2 gap-4">
								<div>
									<p className="text-xs font-semibold text-gray-700 uppercase tracking-wider mb-2">Pending Queries</p>
									{state.pending_queries?.length ? (
										<ul className="space-y-2">
											{state.pending_queries.map((q: string, idx: number) => (
												<li key={`${q}-${idx}`} className="text-sm text-gray-700 bg-yellow-50 border border-yellow-200 rounded p-2">
													{q}
												</li>
											))}
										</ul>
									) : (
										<p className="text-sm text-gray-500">No pending queries.</p>
									)}
								</div>
								<div>
									<p className="text-xs font-semibold text-gray-700 uppercase tracking-wider mb-2">Completed Queries</p>
									{state.completed_queries?.length ? (
										<ul className="space-y-2">
											{state.completed_queries.map((q: string, idx: number) => (
												<li key={`${q}-${idx}`} className="text-sm text-gray-700 bg-green-50 border border-green-200 rounded p-2">
													{q}
												</li>
											))}
										</ul>
									) : (
										<p className="text-sm text-gray-500">No completed queries yet.</p>
									)}
								</div>
							</div>

							<div>
								<p className="text-xs font-semibold text-gray-700 uppercase tracking-wider mb-2">Reasoning Log</p>
								{state.reasoning_log?.length ? (
									<div className="max-h-64 overflow-auto border border-gray-200 rounded">
										{state.reasoning_log.map((entry: unknown, idx: number) => (
											<div key={idx} className="px-3 py-2 border-b border-gray-100 last:border-0">
												<p className="text-xs text-gray-500">Step {idx + 1}</p>
												<pre className="text-xs text-gray-700 whitespace-pre-wrap">{JSON.stringify(entry, null, 2)}</pre>
											</div>
										))}
									</div>
								) : (
									<p className="text-sm text-gray-500">No reasoning history available yet.</p>
								)}
							</div>

							<div className="bg-blue-50 border border-blue-200 rounded p-3">
								<p className="text-xs font-semibold text-blue-800 uppercase tracking-wider">Checkpoint Browser</p>
								<p className="mt-1 text-sm text-blue-700">
									Checkpoint browsing and restart actions are planned for the next Sprint 4 increment.
								</p>
							</div>
						</>
					)}
				</div>
			)}
		</div>
	);
}
