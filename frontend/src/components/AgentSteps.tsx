import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import type { AgentStepsResponse } from '../types';

interface Props {
	researchId: number;
}

export default function AgentSteps({ researchId }: Props) {
	const [stepsData, setStepsData] = useState<AgentStepsResponse | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [expandedStep, setExpandedStep] = useState<number | null>(null);

	const loadSteps = useCallback(async () => {
		try {
			const data = await api.getAgentSteps(researchId);
			setStepsData(data);
			setError(null);
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Failed to load steps');
		} finally {
			setLoading(false);
		}
	}, [researchId]);

	useEffect(() => {
		loadSteps();
		// Poll while research is in progress
		const interval = setInterval(loadSteps, 5000);
		return () => clearInterval(interval);
	}, [researchId, loadSteps]);

	const getStepIcon = (stepType: string) => {
		switch (stepType) {
			case 'planning': return '📋';
			case 'searching': return '🔍';
			case 'relevance_filter': return '🎯';
			case 'thinking': return '🧠';
			case 'hypothesis': return '💡';
			case 'synthesis': return '📝';
			case 'formatting': return '📄';
			case 'summary': return '📊';
			case 'error': return '❌';
			default: return '📌';
		}
	};

	const getStatusBadge = (status: string) => {
		switch (status) {
			case 'running':
				return (
					<span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
						<span className="w-1.5 h-1.5 mr-1 rounded-full bg-blue-500 animate-pulse" />
						Running
					</span>
				);
			case 'completed':
				return (
					<span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
						✓ Done
					</span>
				);
			case 'skipped':
				return (
					<span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
						⏭ Skipped
					</span>
				);
			case 'error':
				return (
					<span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
						✗ Error
					</span>
				);
			default:
				return null;
		}
	};

	const getStepTypeLabel = (stepType: string) => {
		switch (stepType) {
			case 'planning': return 'Planning';
			case 'searching': return 'Search';
			case 'relevance_filter': return 'Relevance Filter';
			case 'thinking': return 'Thinking';
			case 'hypothesis': return 'Hypothesis';
			case 'synthesis': return 'Synthesis';
			case 'formatting': return 'Formatting';
			case 'summary': return 'Summary';
			case 'error': return 'Error';
			default: return stepType;
		}
	};

	const getStepTypeBgColor = (stepType: string) => {
		switch (stepType) {
			case 'planning': return 'bg-indigo-50 border-indigo-200';
			case 'searching': return 'bg-blue-50 border-blue-200';
			case 'thinking': return 'bg-purple-50 border-purple-200';
			case 'hypothesis': return 'bg-amber-50 border-amber-200';
			case 'synthesis': return 'bg-emerald-50 border-emerald-200';
			case 'formatting': return 'bg-teal-50 border-teal-200';
			case 'summary': return 'bg-gray-50 border-gray-200';
			case 'error': return 'bg-red-50 border-red-200';
			default: return 'bg-gray-50 border-gray-200';
		}
	};

	const renderMetadata = (metadata: Record<string, unknown>) => {
		if (!metadata || Object.keys(metadata).length === 0) return null;

		return (
			<div className="mt-2 text-xs">
				{Object.entries(metadata).map(([key, value]) => {
					const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

					if (Array.isArray(value)) {
						if (value.length === 0) return null;
						return (
							<div key={key} className="mt-1">
								<span className="font-medium text-gray-600">{label}:</span>
								<ul className="ml-4 mt-0.5 list-disc text-gray-500">
									{value.slice(0, 10).map((item, i) => (
										<li key={i}>{typeof item === 'string' ? item : JSON.stringify(item)}</li>
									))}
									{value.length > 10 && <li>... and {value.length - 10} more</li>}
								</ul>
							</div>
						);
					}

					if (typeof value === 'object' && value !== null) {
						return (
							<div key={key} className="mt-1">
								<span className="font-medium text-gray-600">{label}:</span>
								<pre className="ml-4 mt-0.5 text-gray-500 overflow-x-auto">
									{JSON.stringify(value, null, 2)}
								</pre>
							</div>
						);
					}

					return (
						<div key={key} className="mt-1">
							<span className="font-medium text-gray-600">{label}:</span>{' '}
							<span className="text-gray-500">
								{value === null || value === undefined ? '—' : String(value)}
							</span>
						</div>
					);
				})}
			</div>
		);
	};

	if (loading) {
		return (
			<div className="text-center text-gray-500 py-8">
				<p>Loading agent steps...</p>
			</div>
		);
	}

	if (error) {
		return (
			<div className="text-sm text-red-600 bg-red-50 p-4 rounded">
				{error}
			</div>
		);
	}

	if (!stepsData || stepsData.steps.length === 0) {
		return (
			<div className="text-center text-gray-500 py-8">
				<p>No agent steps recorded yet.</p>
				{stepsData?.status === 'researching' && (
					<p className="text-sm mt-2">Steps will appear as the agent works.</p>
				)}
			</div>
		);
	}

	return (
		<div className="space-y-3">
			{/* Header */}
			<div className="flex items-center justify-between">
				<div className="text-sm text-gray-600">
					{stepsData.total_steps} steps recorded
				</div>
				<button
					onClick={loadSteps}
					className="text-xs text-blue-600 hover:text-blue-800 transition-colors"
				>
					↻ Refresh
				</button>
			</div>

			{/* Steps timeline */}
			<div className="relative">
				{/* Timeline line */}
				<div className="absolute left-5 top-0 bottom-0 w-0.5 bg-gray-200" />

				<div className="space-y-3">
					{stepsData.steps.map((step, index) => (
						<div
							key={index}
							className={`relative pl-12 cursor-pointer`}
							onClick={() => setExpandedStep(expandedStep === index ? null : index)}
						>
							{/* Timeline dot */}
							<div className="absolute left-3 top-3 w-5 h-5 flex items-center justify-center text-sm">
								{getStepIcon(step.step_type)}
							</div>

							<div className={`border rounded-lg p-3 transition-all ${getStepTypeBgColor(step.step_type)} ${expandedStep === index ? 'ring-2 ring-blue-300' : 'hover:shadow-sm'}`}>
								{/* Step header */}
								<div className="flex items-center justify-between">
									<div className="flex items-center gap-2">
										<span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
											{getStepTypeLabel(step.step_type)}
										</span>
										{getStatusBadge(step.status)}
									</div>
									<span className="text-xs text-gray-400">
										{new Date(step.timestamp).toLocaleTimeString()}
									</span>
								</div>

								{/* Step title */}
								<div className="mt-1 text-sm font-medium text-gray-900">
									{step.title}
								</div>

								{/* Step description (always visible) */}
								{step.description && (
									<div className="mt-1 text-sm text-gray-600">
										{step.description}
									</div>
								)}

								{/* Expanded metadata */}
								{expandedStep === index && step.metadata && Object.keys(step.metadata).length > 0 && (
									<div className="mt-2 pt-2 border-t border-gray-200">
										<div className="text-xs font-medium text-gray-500 mb-1">Details</div>
										{renderMetadata(step.metadata)}
									</div>
								)}

								{/* Expand hint */}
								{step.metadata && Object.keys(step.metadata).length > 0 && expandedStep !== index && (
									<div className="mt-1 text-xs text-gray-400">
										Click to see details →
									</div>
								)}
							</div>
						</div>
					))}
				</div>
			</div>
		</div>
	);
}
