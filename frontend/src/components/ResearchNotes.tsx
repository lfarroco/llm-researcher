import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import type { ResearchNote } from '../types';

interface Props {
	researchId: number;
}

const CATEGORIES = ['observation', 'gap', 'pattern', 'contradiction', 'instruction', 'summary'] as const;

const CATEGORY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
	observation: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
	gap: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
	pattern: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
	contradiction: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
	instruction: { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200' },
	summary: { bg: 'bg-gray-50', text: 'text-gray-700', border: 'border-gray-200' },
};

const AGENT_LABELS: Record<string, string> = {
	planner: 'Planner',
	search: 'Search Agent',
	hypothesis: 'Hypothesis Agent',
	synthesis: 'Synthesis Agent',
	user: 'You',
};

export default function ResearchNotes({ researchId }: Props) {
	const [notes, setNotes] = useState<ResearchNote[]>([]);
	const [loading, setLoading] = useState(true);
	const [newContent, setNewContent] = useState('');
	const [newCategory, setNewCategory] = useState<string>('observation');
	const [editingId, setEditingId] = useState<number | null>(null);
	const [editContent, setEditContent] = useState('');
	const [filterAgent, setFilterAgent] = useState<string>('');
	const [filterCategory, setFilterCategory] = useState<string>('');

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
				category: newCategory,
				content: newContent.trim(),
			});
			setNewContent('');
			loadNotes();
		} catch {
			alert('Failed to create note');
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
			alert('Failed to update note');
		}
	};

	const handleDelete = async (noteId: number) => {
		if (!confirm('Delete this note?')) return;
		try {
			await api.deleteNote(researchId, noteId);
			loadNotes();
		} catch {
			alert('Failed to delete note');
		}
	};

	const startEdit = (note: ResearchNote) => {
		setEditingId(note.id);
		setEditContent(note.content);
	};

	const filteredNotes = notes.filter((n) => {
		if (filterAgent && n.agent !== filterAgent) return false;
		if (filterCategory && n.category !== filterCategory) return false;
		return true;
	});

	const agents = [...new Set(notes.map((n) => n.agent))];
	const categories = [...new Set(notes.map((n) => n.category))];

	if (loading) {
		return <p className="text-center text-gray-500 py-8">Loading notes...</p>;
	}

	return (
		<div className="space-y-6">
			{/* Add note form */}
			<form onSubmit={handleCreate} className="border rounded-lg p-4 bg-gray-50">
				<h3 className="text-sm font-semibold text-gray-700 mb-3">Add a note</h3>
				<div className="flex gap-2 mb-3">
					<select
						value={newCategory}
						onChange={(e) => setNewCategory(e.target.value)}
						className="text-sm border rounded px-2 py-1.5 bg-white"
					>
						{CATEGORIES.map((cat) => (
							<option key={cat} value={cat}>
								{cat}
							</option>
						))}
					</select>
				</div>
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
					<select
						value={filterCategory}
						onChange={(e) => setFilterCategory(e.target.value)}
						className="border rounded px-2 py-1 text-sm bg-white"
					>
						<option value="">All categories</option>
						{categories.map((c) => (
							<option key={c} value={c}>
								{c}
							</option>
						))}
					</select>
					{(filterAgent || filterCategory) && (
						<button
							onClick={() => {
								setFilterAgent('');
								setFilterCategory('');
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
						const colors = CATEGORY_COLORS[note.category] || CATEGORY_COLORS.observation;
						const isEditing = editingId === note.id;

						return (
							<div
								key={note.id}
								className={`border ${colors.border} rounded-lg p-4 ${colors.bg}`}
							>
								<div className="flex items-start justify-between gap-2">
									<div className="flex items-center gap-2 text-xs mb-2">
										<span className={`font-medium ${colors.text}`}>
											{AGENT_LABELS[note.agent] || note.agent}
										</span>
										<span className={`px-1.5 py-0.5 rounded ${colors.text} bg-white/50 font-medium`}>
											{note.category}
										</span>
										<span className="text-gray-400">
											{new Date(note.created_at).toLocaleString()}
										</span>
									</div>
									{note.agent === 'user' && (
										<div className="flex gap-1">
											<button
												onClick={() => (isEditing ? handleUpdate(note.id) : startEdit(note))}
												className="text-xs text-gray-400 hover:text-gray-600"
											>
												{isEditing ? 'Save' : 'Edit'}
											</button>
											{isEditing && (
												<button
													onClick={() => setEditingId(null)}
													className="text-xs text-gray-400 hover:text-gray-600"
												>
													Cancel
												</button>
											)}
											<button
												onClick={() => handleDelete(note.id)}
												className="text-xs text-red-400 hover:text-red-600"
											>
												Delete
											</button>
										</div>
									)}
								</div>
								{isEditing ? (
									<textarea
										value={editContent}
										onChange={(e) => setEditContent(e.target.value)}
										className="w-full text-sm border rounded px-2 py-1 mt-1"
										rows={3}
									/>
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
