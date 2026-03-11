import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import type { ResearchEntitiesResponse } from '../types';

interface Props {
	researchId: number;
}

const typeStyles: Record<string, string> = {
	method: 'bg-blue-100 text-blue-700',
	material: 'bg-amber-100 text-amber-700',
	metric: 'bg-emerald-100 text-emerald-700',
	finding: 'bg-rose-100 text-rose-700',
	concept: 'bg-violet-100 text-violet-700',
};

export default function ResearchEntitiesTab({ researchId }: Props) {
	const [data, setData] = useState<ResearchEntitiesResponse | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		let mounted = true;
		const loadEntities = async () => {
			try {
				setLoading(true);
				setError(null);
				const result = await api.getEntities(researchId);
				if (mounted) {
					setData(result);
				}
			} catch (err) {
				if (mounted) {
					setError(err instanceof Error ? err.message : 'Failed to load entities');
				}
			} finally {
				if (mounted) {
					setLoading(false);
				}
			}
		};

		loadEntities();
		return () => {
			mounted = false;
		};
	}, [researchId]);

	const grouped = useMemo(() => {
		if (!data?.entities) return {} as Record<string, Array<{ name: string; entity_type: string; mentions: string[]; mention_count: number }>>;
		return data.entities.reduce((acc, entity) => {
			const key = entity.entity_type;
			if (!acc[key]) acc[key] = [];
			acc[key].push(entity);
			return acc;
		}, {} as Record<string, Array<{ name: string; entity_type: string; mentions: string[]; mention_count: number }>>);
	}, [data]);

	const maxMentions = useMemo(() => {
		if (!data?.entities?.length) return 1;
		return Math.max(...data.entities.map((e) => e.mention_count));
	}, [data]);

	if (loading) {
		return <p className="text-sm text-gray-500">Extracting entities...</p>;
	}

	if (error) {
		return <p className="text-sm text-red-600">{error}</p>;
	}

	if (!data || data.entities.length === 0) {
		return (
			<div className="text-center py-10">
				<p className="text-gray-500">No entities extracted yet.</p>
				<p className="text-sm text-gray-400 mt-2">
					Add sources/findings with richer text to visualize methods, materials, metrics, and findings.
				</p>
			</div>
		);
	}

	const typeOrder = ['method', 'material', 'metric', 'finding', 'concept'];
	const visibleTypes = typeOrder.filter((t) => grouped[t]?.length);

	return (
		<div className="space-y-6">
			<div className="bg-gradient-to-r from-slate-50 to-blue-50 rounded-lg border border-slate-200 p-4">
				<p className="text-sm text-slate-600">Entity map</p>
				<p className="text-2xl font-bold text-slate-900 mt-1">{data.total_entities}</p>
				<p className="text-xs text-slate-500 mt-1">Detected from sources and findings</p>
			</div>

			{visibleTypes.map((type) => (
				<section key={type} className="space-y-3">
					<div className="flex items-center justify-between">
						<h4 className="text-sm font-semibold text-gray-800 capitalize">{type}</h4>
						<span className={`px-2 py-1 text-xs rounded-full ${typeStyles[type] || 'bg-gray-100 text-gray-700'}`}>
							{grouped[type].length}
						</span>
					</div>

					<div className="grid gap-3 md:grid-cols-2">
						{grouped[type].map((entity) => {
							const width = Math.max(8, Math.round((entity.mention_count / maxMentions) * 100));
							return (
								<div key={`${type}-${entity.name}`} className="border border-gray-200 rounded-lg p-3 bg-white">
									<div className="flex items-start justify-between gap-2">
										<p className="text-sm font-medium text-gray-900 break-words">{entity.name}</p>
										<span className="text-xs text-gray-500 whitespace-nowrap">{entity.mention_count} mention{entity.mention_count !== 1 ? 's' : ''}</span>
									</div>
									<div className="h-2 bg-gray-100 rounded mt-2 overflow-hidden">
										<div className="h-full bg-blue-500 rounded" style={{ width: `${width}%` }} />
									</div>
									{entity.mentions.length > 0 && (
										<div className="mt-2 flex flex-wrap gap-1">
											{entity.mentions.slice(0, 3).map((m) => (
												<span key={`${entity.name}-${m}`} className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded">
													{m}
												</span>
											))}
										</div>
									)}
								</div>
							);
						})}
					</div>
				</section>
			))}
		</div>
	);
}
