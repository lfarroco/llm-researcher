import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import type { ResearchPlan } from '../types';
import { useToast } from '../hooks/useToast';

interface Props {
	researchId: number;
	researchQuery: string;
}

export default function ResearchPlanTab({ researchId, researchQuery }: Props) {
	const [plan, setPlan] = useState<ResearchPlan | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const { showToast } = useToast();
	const [newQuery, setNewQuery] = useState('');
	const [saving, setSaving] = useState(false);

	const loadPlan = useCallback(async () => {
		try {
			setLoading(true);
			setError(null);
			const data = await api.getPlan(researchId);
			setPlan(data);
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Failed to load plan');
		} finally {
			setLoading(false);
		}
	}, [researchId]);

	useEffect(() => {
		loadPlan();
	}, [loadPlan]);

	const completedCount = useMemo(() => {
		if (!plan) return 0;
		return plan.sub_queries.filter((q) => plan.progress[q]?.status === 'completed').length;
	}, [plan]);

	const handleAddSubQuery = async () => {
		const query = newQuery.trim();
		if (!query) return;
		if (saving) return;

		try {
			setSaving(true);
			const updated = await api.updatePlan(researchId, {
				add_queries: [query],
			});
			setPlan(updated);
			setNewQuery('');
		} catch (err) {
			showToast(
				err instanceof Error ? err.message : 'Failed to add sub-query',
				'error'
			);
		} finally {
			setSaving(false);
		}
	};

	const handleRemoveSubQuery = async (query: string) => {
		if (saving) return;
		const confirmed = window.confirm(
			`Remove this sub-query? This may reduce coverage for the final answer.\n\n"${query}"`
		);
		if (!confirmed) return;

		try {
			setSaving(true);
			const updated = await api.updatePlan(researchId, {
				remove_queries: [query],
			});
			setPlan(updated);
		} catch (err) {
			showToast(
				err instanceof Error ? err.message : 'Failed to remove sub-query',
				'error'
			);
		} finally {
			setSaving(false);
		}
	};

	if (loading) {
		return <p className="text-sm text-gray-500">Loading research plan...</p>;
	}

	if (error) {
		return <p className="text-sm text-red-600">{error}</p>;
	}

	if (!plan) {
		return <p className="text-sm text-gray-500">No plan data available.</p>;
	}

	return (
		<div className="space-y-5">
			<div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
				<h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider">Main Research Question</h3>
				<p className="mt-2 text-gray-900">{plan.query || researchQuery}</p>
				{plan.refined_question && (
					<p className="mt-2 text-sm text-gray-600">
						<span className="font-medium text-gray-700">Refined:</span> {plan.refined_question}
					</p>
				)}
				<p className="mt-3 text-xs text-gray-600">
					Progress: {completedCount}/{plan.sub_queries.length} sub-queries completed
				</p>
			</div>

			<div className="flex gap-2">
				<input
					type="text"
					value={newQuery}
					onChange={(e) => setNewQuery(e.target.value)}
					onKeyDown={(e) => {
						if (e.key === 'Enter') {
							e.preventDefault();
							handleAddSubQuery();
						}
					}}
					placeholder="Add a sub-query..."
					className="flex-1 px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
					disabled={saving}
				/>
				<button
					onClick={handleAddSubQuery}
					disabled={saving || !newQuery.trim()}
					className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
				>
					Add Sub-query
				</button>
			</div>

			{plan.sub_queries.length === 0 ? (
				<div className="text-center py-10 border border-dashed border-gray-300 rounded-lg">
					<p className="text-sm text-gray-500">No sub-queries yet. Add one to start structuring this research.</p>
				</div>
			) : (
				<div className="space-y-3">
					{plan.sub_queries.map((query, index) => {
						const progress = plan.progress[query];
						const isDone = progress?.status === 'completed';

						return (
							<div key={`${query}-${index}`} className="border border-gray-200 rounded-lg p-4">
								<div className="flex items-start justify-between gap-4">
									<div>
										<div className="flex items-center gap-2">
											<span className="text-xs font-semibold text-gray-500">#{index + 1}</span>
											<span
												className={`px-2 py-0.5 rounded text-xs font-medium ${isDone
														? 'bg-green-100 text-green-700'
														: 'bg-yellow-100 text-yellow-700'
													}`}
											>
												{isDone ? 'Completed' : 'Pending'}
											</span>
										</div>
										<p className="mt-2 text-sm text-gray-900">{query}</p>
										{progress?.finding && (
											<p className="mt-2 text-xs text-gray-600 bg-gray-50 rounded p-2">
												{progress.finding}
											</p>
										)}
									</div>
									<button
										onClick={() => handleRemoveSubQuery(query)}
										disabled={saving}
										className="text-xs px-2 py-1 rounded border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-50"
									>
										Remove
									</button>
								</div>
							</div>
						);
					})}
				</div>
			)}
		</div>
	);
}
