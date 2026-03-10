import type { Research } from '../types';

interface Props {
	researches: Research[];
	selectedId: number | null;
	onSelect: (id: number) => void;
	loading: boolean;
}

const statusColors: Record<string, string> = {
	pending: 'bg-gray-100 text-gray-700',
	researching: 'bg-blue-100 text-blue-700',
	completed: 'bg-green-100 text-green-700',
	failed: 'bg-red-100 text-red-700',
	error: 'bg-red-100 text-red-700',
	cancelled: 'bg-orange-100 text-orange-700',
};

const statusIcons: Record<string, string> = {
	pending: '⏳',
	researching: '🔍',
	completed: '✅',
	failed: '❌',
	error: '❌',
	cancelled: '⚠️',
};

export default function ResearchList({ researches, selectedId, onSelect, loading }: Props) {
	if (loading && researches.length === 0) {
		return (
			<div className="bg-white rounded-lg shadow p-6">
				<h2 className="text-lg font-semibold mb-4">Research History</h2>
				<div className="text-center text-gray-500 py-8">
					Loading...
				</div>
			</div>
		);
	}

	if (researches.length === 0) {
		return (
			<div className="bg-white rounded-lg shadow p-6">
				<h2 className="text-lg font-semibold mb-4">Research History</h2>
				<div className="text-center text-gray-500 py-8">
					<p>No research queries yet</p>
					<p className="text-sm mt-2">Create one to get started</p>
				</div>
			</div>
		);
	}

	return (
		<div className="bg-white rounded-lg shadow">
			<div className="p-4 border-b">
				<h2 className="text-lg font-semibold">Research History</h2>
				<p className="text-sm text-gray-600">{researches.length} queries</p>
			</div>

			<div className="divide-y max-h-[600px] overflow-y-auto">
				{researches.map((research) => (
					<button
						key={research.id}
						onClick={() => onSelect(research.id)}
						className={`w-full text-left p-4 hover:bg-gray-50 transition-colors ${selectedId === research.id ? 'bg-blue-50' : ''
							}`}
					>
						<div className="flex items-start justify-between gap-2">
							<div className="flex-1 min-w-0">
								<p className="text-sm font-medium text-gray-900 truncate">
									{research.query}
								</p>
								<p className="text-xs text-gray-500 mt-1">
									{new Date(research.created_at).toLocaleDateString()}
								</p>
							</div>
							<span
								className={`px-2 py-1 text-xs rounded-full flex items-center gap-1 ${statusColors[research.status]
									}`}
							>
								<span>{statusIcons[research.status]}</span>
								<span>{research.status}</span>
							</span>
						</div>

						{research.user_notes && (
							<p className="text-xs text-gray-600 mt-2 line-clamp-2">
								{research.user_notes}
							</p>
						)}
					</button>
				))}
			</div>
		</div>
	);
}
