import { useState, useEffect } from 'react';
import type { Source } from '../types';

interface Props {
	isOpen: boolean;
	source?: Source | null;
	onClose: () => void;
	onSubmit: (sourceData: {
		url: string;
		title?: string;
		author?: string;
		content_snippet?: string;
		source_type?: string;
		relevance_score?: number;
		user_notes?: string;
		tags?: string[];
	}) => Promise<void>;
}

export default function SourceFormModal({ isOpen, source, onClose, onSubmit }: Props) {
	const [formData, setFormData] = useState({
		url: '',
		title: '',
		author: '',
		content_snippet: '',
		source_type: 'web',
		relevance_score: 0.5,
		user_notes: '',
		tags: [] as string[],
	});
	const [tagInput, setTagInput] = useState('');
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);

	// Update form when source prop changes (for editing)
	useEffect(() => {
		if (source) {
			setFormData({
				url: source.url,
				title: source.title || '',
				author: source.author || '',
				content_snippet: source.content_snippet || '',
				source_type: source.source_type,
				relevance_score: source.relevance_score,
				user_notes: source.user_notes || '',
				tags: source.tags || [],
			});
		} else {
			// Reset form for new source
			setFormData({
				url: '',
				title: '',
				author: '',
				content_snippet: '',
				source_type: 'web',
				relevance_score: 0.5,
				user_notes: '',
				tags: [],
			});
		}
		setError(null);
	}, [source, isOpen]);

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setIsSubmitting(true);
		setError(null);

		try {
			// Only send non-empty fields
			const dataToSubmit: {
				url: string;
				title?: string;
				author?: string;
				content_snippet?: string;
				source_type?: string;
				relevance_score?: number;
				user_notes?: string;
				tags?: string[];
			} = {
				url: formData.url,
			};

			if (formData.title) dataToSubmit.title = formData.title;
			if (formData.author) dataToSubmit.author = formData.author;
			if (formData.content_snippet) dataToSubmit.content_snippet = formData.content_snippet;
			if (formData.source_type) dataToSubmit.source_type = formData.source_type;
			if (formData.relevance_score !== 0.5) dataToSubmit.relevance_score = formData.relevance_score;
			if (formData.user_notes) dataToSubmit.user_notes = formData.user_notes;
			if (formData.tags.length > 0) dataToSubmit.tags = formData.tags;

			await onSubmit(dataToSubmit);
			onClose();
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Failed to save source');
		} finally {
			setIsSubmitting(false);
		}
	};

	const handleAddTag = () => {
		const tag = tagInput.trim();
		if (tag && !formData.tags.includes(tag)) {
			setFormData((prev) => ({
				...prev,
				tags: [...prev.tags, tag],
			}));
			setTagInput('');
		}
	};

	const handleRemoveTag = (tagToRemove: string) => {
		setFormData((prev) => ({
			...prev,
			tags: prev.tags.filter((tag) => tag !== tagToRemove),
		}));
	};

	const handleTagInputKeyDown = (e: React.KeyboardEvent) => {
		if (e.key === 'Enter') {
			e.preventDefault();
			handleAddTag();
		}
	};

	if (!isOpen) return null;

	const sourceTypes = ['web', 'arxiv', 'wikipedia', 'pubmed', 'semantic_scholar', 'crossref', 'openalex'];

	return (
		<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
			<div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
				<div className="p-6 border-b sticky top-0 bg-white">
					<h2 className="text-xl font-semibold text-gray-900">
						{source ? 'Edit Source' : 'Add Source'}
					</h2>
				</div>

				<form onSubmit={handleSubmit} className="p-6 space-y-4">
					{error && (
						<div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
							{error}
						</div>
					)}

					<div>
						<label className="block text-sm font-medium text-gray-700 mb-1">
							URL <span className="text-red-500">*</span>
						</label>
						<input
							type="url"
							required
							disabled={!!source} // Don't allow URL editing for existing sources
							value={formData.url}
							onChange={(e) => setFormData((prev) => ({ ...prev, url: e.target.value }))}
							className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
							placeholder="https://example.com/article"
						/>
						{source && (
							<p className="mt-1 text-xs text-gray-500">URL cannot be changed for existing sources</p>
						)}
					</div>

					<div>
						<label className="block text-sm font-medium text-gray-700 mb-1">
							Title
						</label>
						<input
							type="text"
							value={formData.title}
							onChange={(e) => setFormData((prev) => ({ ...prev, title: e.target.value }))}
							className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
							placeholder="Source title"
						/>
					</div>

					<div>
						<label className="block text-sm font-medium text-gray-700 mb-1">
							Author
						</label>
						<input
							type="text"
							value={formData.author}
							onChange={(e) => setFormData((prev) => ({ ...prev, author: e.target.value }))}
							className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
							placeholder="Author name(s)"
						/>
					</div>

					<div>
						<label className="block text-sm font-medium text-gray-700 mb-1">
							Source Type
						</label>
						<select
							value={formData.source_type}
							onChange={(e) => setFormData((prev) => ({ ...prev, source_type: e.target.value }))}
							className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
						>
							{sourceTypes.map((type) => (
								<option key={type} value={type}>
									{type}
								</option>
							))}
						</select>
					</div>

					<div>
						<label className="block text-sm font-medium text-gray-700 mb-1">
							Relevance Score: {formData.relevance_score.toFixed(2)}
						</label>
						<input
							type="range"
							min="0"
							max="1"
							step="0.1"
							value={formData.relevance_score}
							onChange={(e) =>
								setFormData((prev) => ({ ...prev, relevance_score: parseFloat(e.target.value) }))
							}
							className="w-full"
						/>
						<div className="flex justify-between text-xs text-gray-500 mt-1">
							<span>Low (0.0)</span>
							<span>High (1.0)</span>
						</div>
					</div>

					<div>
						<label className="block text-sm font-medium text-gray-700 mb-1">
							Content Snippet
						</label>
						<textarea
							value={formData.content_snippet}
							onChange={(e) => setFormData((prev) => ({ ...prev, content_snippet: e.target.value }))}
							className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
							rows={3}
							placeholder="Brief excerpt or summary..."
						/>
					</div>

					<div>
						<label className="block text-sm font-medium text-gray-700 mb-1">
							Notes
						</label>
						<textarea
							value={formData.user_notes}
							onChange={(e) => setFormData((prev) => ({ ...prev, user_notes: e.target.value }))}
							className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
							rows={3}
							placeholder="Your notes about this source..."
						/>
					</div>

					<div>
						<label className="block text-sm font-medium text-gray-700 mb-1">
							Tags
						</label>
						<div className="flex gap-2 mb-2">
							<input
								type="text"
								value={tagInput}
								onChange={(e) => setTagInput(e.target.value)}
								onKeyDown={handleTagInputKeyDown}
								className="flex-1 px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
								placeholder="Add tag..."
							/>
							<button
								type="button"
								onClick={handleAddTag}
								className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 transition-colors"
							>
								Add
							</button>
						</div>
						{formData.tags.length > 0 && (
							<div className="flex flex-wrap gap-2">
								{formData.tags.map((tag) => (
									<span
										key={tag}
										className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-700 text-sm rounded"
									>
										{tag}
										<button
											type="button"
											onClick={() => handleRemoveTag(tag)}
											className="text-blue-600 hover:text-blue-800"
										>
											×
										</button>
									</span>
								))}
							</div>
						)}
					</div>

					<div className="flex gap-3 pt-4 border-t">
						<button
							type="button"
							onClick={onClose}
							disabled={isSubmitting}
							className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded hover:bg-gray-50 transition-colors disabled:opacity-50"
						>
							Cancel
						</button>
						<button
							type="submit"
							disabled={isSubmitting}
							className="flex-1 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors disabled:opacity-50"
						>
							{isSubmitting ? 'Saving...' : source ? 'Update Source' : 'Add Source'}
						</button>
					</div>
				</form>
			</div>
		</div>
	);
}
