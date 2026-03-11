import { useState, useEffect } from 'react';
import type { Finding, Source } from '../types';

interface Props {
	isOpen: boolean;
	finding?: Finding | null;
	sources: Source[];
	onClose: () => void;
	onSubmit: (findingData: {
		content: string;
		source_ids?: number[];
	}) => Promise<void>;
}

export default function FindingFormModal({ isOpen, finding, sources, onClose, onSubmit }: Props) {
	const [formData, setFormData] = useState({
		content: '',
		source_ids: [] as number[],
	});
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);

	// Update form when finding prop changes (for editing)
	useEffect(() => {
		if (finding) {
			setFormData({
				content: finding.content,
				source_ids: finding.source_ids || [],
			});
		} else {
			// Reset form for new finding
			setFormData({
				content: '',
				source_ids: [],
			});
		}
		setError(null);
	}, [finding, isOpen]);

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!formData.content.trim()) {
			setError('Content is required');
			return;
		}

		setIsSubmitting(true);
		setError(null);

		try {
			await onSubmit({
				content: formData.content.trim(),
				source_ids: formData.source_ids.length > 0 ? formData.source_ids : undefined,
			});
			onClose();
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Failed to save finding');
		} finally {
			setIsSubmitting(false);
		}
	};

	const handleToggleSource = (sourceId: number) => {
		setFormData((prev) => ({
			...prev,
			source_ids: prev.source_ids.includes(sourceId)
				? prev.source_ids.filter((id) => id !== sourceId)
				: [...prev.source_ids, sourceId],
		}));
	};

	if (!isOpen) return null;

	return (
		<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
			<div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
				<div className="p-6 border-b sticky top-0 bg-white">
					<h2 className="text-xl font-semibold text-gray-900">
						{finding ? 'Edit Finding' : 'Add Finding'}
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
							Content <span className="text-red-500">*</span>
						</label>
						<textarea
							required
							value={formData.content}
							onChange={(e) => setFormData((prev) => ({ ...prev, content: e.target.value }))}
							className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
							rows={6}
							placeholder="Enter the finding content..."
						/>
						<p className="mt-1 text-xs text-gray-500">
							Describe what you've discovered or learned
						</p>
					</div>

					<div>
						<label className="block text-sm font-medium text-gray-700 mb-2">
							Link to Sources (optional)
						</label>
						{sources.length === 0 ? (
							<p className="text-sm text-gray-500 italic">No sources available</p>
						) : (
							<div className="border border-gray-300 rounded max-h-64 overflow-y-auto">
								<div className="divide-y divide-gray-200">
									{sources.map((source) => (
										<label
											key={source.id}
											className="flex items-start gap-3 p-3 hover:bg-gray-50 cursor-pointer"
										>
											<input
												type="checkbox"
												checked={formData.source_ids.includes(source.id)}
												onChange={() => handleToggleSource(source.id)}
												className="mt-1 h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
											/>
											<div className="flex-1 min-w-0">
												<p className="text-sm font-medium text-gray-900 truncate">
													{source.title}
												</p>
												<p className="text-xs text-gray-500 truncate">
													{source.url}
												</p>
												<span className="inline-block mt-1 px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded">
													{source.source_type}
												</span>
											</div>
										</label>
									))}
								</div>
							</div>
						)}
						{formData.source_ids.length > 0 && (
							<p className="mt-2 text-xs text-gray-600">
								{formData.source_ids.length} source{formData.source_ids.length !== 1 ? 's' : ''} selected
							</p>
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
							disabled={isSubmitting || !formData.content.trim()}
							className="flex-1 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors disabled:opacity-50"
						>
							{isSubmitting ? 'Saving...' : finding ? 'Update Finding' : 'Add Finding'}
						</button>
					</div>
				</form>
			</div>
		</div>
	);
}
