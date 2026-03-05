import { useState } from 'react';
import { api } from '../api/client';
import type { Research } from '../types';

interface Props {
	onResearchCreated: (research: Research) => void;
}

export default function ResearchForm({ onResearchCreated }: Props) {
	const [query, setQuery] = useState('');
	const [notes, setNotes] = useState('');
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!query.trim()) return;

		try {
			setLoading(true);
			setError(null);
			const research = await api.createResearch(query, notes || undefined);
			onResearchCreated(research);
			setQuery('');
			setNotes('');
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Failed to create research');
		} finally {
			setLoading(false);
		}
	};

	return (
		<div className="bg-white rounded-lg shadow p-6">
			<h2 className="text-lg font-semibold mb-4">New Research Query</h2>

			<form onSubmit={handleSubmit} className="space-y-4">
				<div>
					<label htmlFor="query" className="block text-sm font-medium text-gray-700 mb-1">
						Research Question
					</label>
					<input
						id="query"
						type="text"
						value={query}
						onChange={(e) => setQuery(e.target.value)}
						placeholder="What would you like to research?"
						className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
						disabled={loading}
					/>
				</div>

				<div>
					<label htmlFor="notes" className="block text-sm font-medium text-gray-700 mb-1">
						Notes (Optional)
					</label>
					<textarea
						id="notes"
						value={notes}
						onChange={(e) => setNotes(e.target.value)}
						placeholder="Add any notes or context..."
						rows={2}
						className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
						disabled={loading}
					/>
				</div>

				{error && (
					<div className="text-sm text-red-600">
						{error}
					</div>
				)}

				<button
					type="submit"
					disabled={loading || !query.trim()}
					className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
				>
					{loading ? 'Creating...' : 'Start Research'}
				</button>
			</form>
		</div>
	);
}
