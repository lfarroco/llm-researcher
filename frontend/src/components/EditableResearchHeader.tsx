import { useState } from 'react';
import type { Research } from '../types';

interface Props {
	research: Research;
	onUpdate: (updatedResearch: Research) => void;
	onUpdateQuery: (query: string) => Promise<void>;
}

export default function EditableResearchHeader({
	research,
	onUpdate,
	onUpdateQuery,
}: Props) {
	const [isEditingQuery, setIsEditingQuery] = useState(false);
	const [editedQuery, setEditedQuery] = useState(research.query);
	const [isSaving, setIsSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const handleStartEdit = () => {
		setEditedQuery(research.query);
		setIsEditingQuery(true);
		setError(null);
	};

	const handleCancelEdit = () => {
		setEditedQuery(research.query);
		setIsEditingQuery(false);
		setError(null);
	};

	const handleSave = async () => {
		if (editedQuery.trim() === '') {
			setError('Query cannot be empty');
			return;
		}

		if (editedQuery === research.query) {
			setIsEditingQuery(false);
			return;
		}

		if (
			!confirm(
				'Are you sure you want to change the research query? This may affect the context of existing sources and findings.'
			)
		) {
			return;
		}

		try {
			setIsSaving(true);
			setError(null);
			await onUpdateQuery(editedQuery);
			setIsEditingQuery(false);
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Failed to update query');
		} finally {
			setIsSaving(false);
		}
	};

	const handleKeyDown = (e: React.KeyboardEvent) => {
		if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
			handleSave();
		} else if (e.key === 'Escape') {
			handleCancelEdit();
		}
	};

	return (
		<div className="flex-1">
			{isEditingQuery ? (
				<div className="space-y-2">
					<input
						type="text"
						value={editedQuery}
						onChange={(e) => setEditedQuery(e.target.value)}
						onKeyDown={handleKeyDown}
						className="w-full text-xl font-semibold text-gray-900 border-2 border-blue-500 rounded px-3 py-2 focus:outline-none focus:border-blue-600"
						autoFocus
						disabled={isSaving}
					/>
					<div className="flex items-center gap-2">
						<button
							onClick={handleSave}
							disabled={isSaving}
							className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 transition-colors"
						>
							{isSaving ? 'Saving...' : 'Save'}
						</button>
						<button
							onClick={handleCancelEdit}
							disabled={isSaving}
							className="px-3 py-1 text-sm text-gray-600 hover:bg-gray-100 rounded disabled:opacity-50 transition-colors"
						>
							Cancel
						</button>
						<span className="text-xs text-gray-500">
							Press Cmd/Ctrl+Enter to save, Esc to cancel
						</span>
					</div>
					{error && <p className="text-sm text-red-600">{error}</p>}
				</div>
			) : (
				<div className="group">
					<h2 className="text-xl font-semibold text-gray-900 inline-flex items-center gap-2">
						{research.query}
						<button
							onClick={handleStartEdit}
							className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-gray-600 transition-opacity"
							title="Edit query"
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
						{research.updated_at !== research.created_at && (
							<span className="text-sm text-gray-500">
								• Updated {new Date(research.updated_at).toLocaleString()}
							</span>
						)}
					</div>
				</div>
			)}
		</div>
	);
}
