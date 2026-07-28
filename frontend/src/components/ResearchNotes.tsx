import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import type { ResearchNote } from '../types';
import { useToast } from '../hooks/useToast';

interface Props {
	researchId: number;
}

const AGENT_LABELS: Record<string, string> = {
	planner: 'Planner',
	search: 'Search Agent',
	hypothesis: 'Hypothesis Agent',
	synthesis: 'Synthesis Agent',
	user: 'You',
};

export default function ResearchNotes({ researchId }: Props) {
	const { showToast } = useToast();
	const [notes, setNotes] = useState<ResearchNote[]>([]);
	const [loading, setLoading] = useState(true);
	const [newContent, setNewContent] = useState('');
	const [editingId, setEditingId] = useState<number | null>(null);
	const [editContent, setEditContent] = useState('');
	const [filterAgent, setFilterAgent] = useState<string>('');

	const loadNotes = useCallback(async () => {
		try {
			setLoading(true);
			const data = await api.getNotes(researchId);
			setNotes(data);
		} catch {
			// silent
		} finally {
			setLoading(false);
		}
	}, [researchId]);

	useEffect(() => {
		loadNotes();
	}, [loadNotes]);

	const handleCreate = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!newContent.trim()) return;
		try {
			await api.createNote(researchId, {
				content: newContent.trim(),
			});
			setNewContent('');
			loadNotes();
		} catch {
			showToast('Failed to create note', 'error');
		}
	};

	const handleUpdate = async (noteId: number) => {
		if (!editContent.trim()) return;
		try {
			await api.updateNote(researchId, noteId, { content: editContent.trim() });
			setEditingId(null);
			setEditContent('');
			loadNotes();
		} catch {
			showToast('Failed to update note', 'error');
		}
	};

	const handleDelete = async (noteId: number) => {
		if (!confirm('Delete this note?')) return;
		try {
			await api.deleteNote(researchId, noteId);
			loadNotes();
		} catch {
			showToast('Failed to delete note', 'error');
		}
	};

	const startEdit = (note: ResearchNote) => {
		setEditingId(note.id);
		setEditContent(note.content);
	};

	const cancelEdit = () => {
		setEditingId(null);
		setEditContent('');
	};

	const filteredNotes = notes.filter((n) => {
		if (filterAgent && n.agent !== filterAgent) return false;
		return true;
	});

	const agents = [...new Set(notes.map((n) => n.agent))];

	if (loading) {
		return <p className="text-center text-gray-500 py-8">Loading notes...</p>;
	}

	return (
		<div className="space-y-6">
			{/* Add note form */}
			<form onSubmit={handleCreate} className="border rounded-lg p-4 bg-gray-50">
				<h3 className="text-sm font-semibold text-gray-700 mb-3">Add a note</h3>
				<div className="flex gap-2">
					<textarea
						value={newContent}
						onChange={(e) => setNewContent(e.target.value)}
						placeholder="Write a research note..."
						className="flex-1 text-sm border rounded px-3 py-2 resize-none"
						rows={2}
					/>
					<button
						type="submit"
						disabled={!newContent.trim()}
						className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 self-end"
					>
						Add
					</button>
				</div>
			</form>

			{/* Filters */}
			{notes.length > 0 && (
				<div className="flex gap-3 items-center text-sm">
					<span className="text-gray-500 font-medium">Filter:</span>
					<select
						value={filterAgent}
						onChange={(e) => setFilterAgent(e.target.value)}
						className="border rounded px-2 py-1 text-sm bg-white"
					>
						<option value="">All agents</option>
						{agents.map((a) => (
							<option key={a} value={a}>
								{AGENT_LABELS[a] || a}
							</option>
						))}
					</select>
					{filterAgent && (
						<button
							onClick={() => {
								setFilterAgent('');
							}}
							className="text-xs text-gray-500 hover:text-gray-700 underline"
						>
							Clear
						</button>
					)}
					<span className="ml-auto text-xs text-gray-400">
						{filteredNotes.length} of {notes.length} notes
					</span>
				</div>
			)}

			{/* Notes list */}
			{filteredNotes.length === 0 ? (
				<p className="text-center text-gray-500 py-8">
					{notes.length === 0
						? 'No notes yet. Notes will appear here as agents work, or you can add your own.'
						: 'No notes match the current filters.'}
				</p>
			) : (
				<div className="space-y-3">
					{filteredNotes.map((note) => {
						const isEditing = editingId === note.id;

						return (
							<div
								key={note.id}
								className="border border-gray-200 rounded-lg p-4 bg-white"
							>
								<div className="flex items-start justify-between gap-2">
									<div className="flex items-center gap-2 text-xs mb-2">
										<span className="font-medium text-gray-700">
											{AGENT_LABELS[note.agent] || note.agent}
										</span>
										<span className="text-gray-400">
											{new Date(note.created_at).toLocaleString()}
										</span>
									</div>
										<div className="flex gap-1">
											{!isEditing && (
												<button
													onClick={() => startEdit(note)}
													className="p-2 text-gray-600 hover:bg-gray-100 rounded transition-colors"
													title="Edit note"
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
											{note.agent === 'user' && !isEditing && (
												<button
													onClick={() => handleDelete(note.id)}
													className="p-2 text-red-600 hover:bg-red-50 rounded transition-colors"
													title="Delete note"
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
															d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M9 7V4a1 1 0 011-1h4a1 1 0 011 1v3m-7 0h8"
														/>
													</svg>
												</button>
											)}
										</div>
								</div>
								{isEditing ? (
										<div className="space-y-2">
											<textarea
												value={editContent}
												onChange={(e) => setEditContent(e.target.value)}
												className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
												rows={3}
											/>
											<div className="flex gap-2">
												<button
													onClick={() => handleUpdate(note.id)}
													disabled={!editContent.trim()}
													className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50 transition-colors"
												>
													Save
												</button>
												<button
													onClick={cancelEdit}
													className="px-3 py-1 border border-gray-300 text-gray-700 text-sm rounded hover:bg-gray-50 transition-colors"
												>
													Cancel
												</button>
											</div>
										</div>
								) : (
									<p className="text-sm text-gray-900 whitespace-pre-wrap">{note.content}</p>
								)}
							</div>
						);
					})}
				</div>
			)}
		</div>
	);
}
