import SearchInput from './SearchInput';
import type { Source } from '../types';

export interface FindingFilters {
	source_id?: number;
	search?: string;
	sort_order?: 'asc' | 'desc';
}

interface Props {
	filters: FindingFilters;
	onFiltersChange: (filters: FindingFilters) => void;
	totalFindings: number;
	sources?: Source[]; // For source filter dropdown
}

const SORT_OPTIONS = [
	{ value: 'desc', label: 'Newest First' },
	{ value: 'asc', label: 'Oldest First' },
];

export default function FindingsFilterBar({ filters, onFiltersChange, totalFindings, sources = [] }: Props) {
	const handleSearchChange = (value: string) => {
		onFiltersChange({ ...filters, search: value });
	};

	const handleSourceFilterChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
		const value = e.target.value ? Number(e.target.value) : undefined;
		onFiltersChange({ ...filters, source_id: value });
	};

	const handleSortChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
		onFiltersChange({
			...filters,
			sort_order: e.target.value as 'asc' | 'desc',
		});
	};

	const hasActiveFilters = filters.source_id || filters.search;

	const handleClearFilters = () => {
		onFiltersChange({
			sort_order: filters.sort_order,
		});
	};

	return (
		<div className="mb-4 space-y-3">
			{/* Search and Dropdowns */}
			<div className="flex gap-3">
				<div className="flex-1">
					<SearchInput
						value={filters.search || ''}
						onChange={handleSearchChange}
						placeholder="Search in finding content..."
					/>
				</div>
				{sources.length > 0 && (
					<select
						value={filters.source_id || ''}
						onChange={handleSourceFilterChange}
						className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
					>
						<option value="">All Sources</option>
						{sources.map((source) => (
							<option key={source.id} value={source.id}>
								{source.title.substring(0, 50)}
								{source.title.length > 50 ? '...' : ''}
							</option>
						))}
					</select>
				)}
				<select
					value={filters.sort_order || 'desc'}
					onChange={handleSortChange}
					className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
				>
					{SORT_OPTIONS.map((option) => (
						<option key={option.value} value={option.value}>
							{option.label}
						</option>
					))}
				</select>
			</div>

			{/* Filter Status */}
			<div className="flex items-center gap-2">
				{hasActiveFilters && (
					<button
						onClick={handleClearFilters}
						className="px-3 py-1 text-sm text-blue-600 hover:text-blue-700 font-medium"
					>
						Clear filters
					</button>
				)}

				<span className="ml-auto text-sm text-gray-500">
					{totalFindings} {totalFindings === 1 ? 'finding' : 'findings'}
				</span>
			</div>
		</div>
	);
}
