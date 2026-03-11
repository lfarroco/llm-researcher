import SearchInput from './SearchInput';

export interface SourceFilters {
	source_type?: string;
	search?: string;
	sort_by?: string;
	sort_order?: 'asc' | 'desc';
	quick_filter?: 'all' | 'academic' | 'recent' | 'no_content';
}

interface Props {
	filters: SourceFilters;
	onFiltersChange: (filters: SourceFilters) => void;
	totalSources: number;
}

const SOURCE_TYPES = [
	{ value: '', label: 'All Types' },
	{ value: 'web', label: 'Web' },
	{ value: 'arxiv', label: 'arXiv' },
	{ value: 'wikipedia', label: 'Wikipedia' },
	{ value: 'pubmed', label: 'PubMed' },
	{ value: 'semantic_scholar', label: 'Semantic Scholar' },
	{ value: 'openalex', label: 'OpenAlex' },
	{ value: 'crossref', label: 'Crossref' },
];

const SORT_OPTIONS = [
	{ value: 'accessed_at_desc', label: 'Newest First' },
	{ value: 'accessed_at_asc', label: 'Oldest First' },
	{ value: 'title_asc', label: 'Title (A-Z)' },
	{ value: 'title_desc', label: 'Title (Z-A)' },
];

export default function SourcesFilterBar({ filters, onFiltersChange, totalSources }: Props) {
	const handleSearchChange = (value: string) => {
		onFiltersChange({ ...filters, search: value });
	};

	const handleSourceTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
		const value = e.target.value || undefined;
		onFiltersChange({ ...filters, source_type: value });
	};

	const handleSortChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
		const [sort_by, sort_order] = e.target.value.split('_');
		const order = sort_order === 'desc' ? 'desc' : 'asc';
		onFiltersChange({
			...filters,
			sort_by: sort_by === 'accessed' ? undefined : sort_by,
			sort_order: order as 'asc' | 'desc',
		});
	};

	const handleQuickFilter = (quickFilter: SourceFilters['quick_filter']) => {
		if (filters.quick_filter === quickFilter) {
			// Deselect if already selected
			onFiltersChange({ ...filters, quick_filter: 'all' });
		} else {
			onFiltersChange({ ...filters, quick_filter: quickFilter });
		}
	};

	const hasActiveFilters =
		filters.source_type ||
		filters.search ||
		(filters.quick_filter && filters.quick_filter !== 'all');

	const handleClearFilters = () => {
		onFiltersChange({
			sort_by: filters.sort_by,
			sort_order: filters.sort_order,
		});
	};

	const currentSortValue = filters.sort_by
		? `${filters.sort_by}_${filters.sort_order || 'desc'}`
		: 'accessed_at_desc';

	return (
		<div className="mb-4 space-y-3">
			{/* Search and Dropdowns */}
			<div className="flex gap-3">
				<div className="flex-1">
					<SearchInput
						value={filters.search || ''}
						onChange={handleSearchChange}
						placeholder="Search in title, author, or content..."
					/>
				</div>
				<select
					value={filters.source_type || ''}
					onChange={handleSourceTypeChange}
					className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
				>
					{SOURCE_TYPES.map((type) => (
						<option key={type.value} value={type.value}>
							{type.label}
						</option>
					))}
				</select>
				<select
					value={currentSortValue}
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

			{/* Quick Filters */}
			<div className="flex items-center gap-2 flex-wrap">
				<span className="text-sm text-gray-600">Quick filters:</span>
				<button
					onClick={() => handleQuickFilter('academic')}
					className={`px-3 py-1 text-sm rounded-full transition-colors ${
						filters.quick_filter === 'academic'
							? 'bg-blue-100 text-blue-700 font-medium'
							: 'bg-gray-100 text-gray-700 hover:bg-gray-200'
					}`}
				>
					Academic Only
				</button>
				<button
					onClick={() => handleQuickFilter('recent')}
					className={`px-3 py-1 text-sm rounded-full transition-colors ${
						filters.quick_filter === 'recent'
							? 'bg-blue-100 text-blue-700 font-medium'
							: 'bg-gray-100 text-gray-700 hover:bg-gray-200'
					}`}
				>
					Recently Added
				</button>
				<button
					onClick={() => handleQuickFilter('no_content')}
					className={`px-3 py-1 text-sm rounded-full transition-colors ${
						filters.quick_filter === 'no_content'
							? 'bg-blue-100 text-blue-700 font-medium'
							: 'bg-gray-100 text-gray-700 hover:bg-gray-200'
					}`}
				>
					No Content
				</button>

				{hasActiveFilters && (
					<button
						onClick={handleClearFilters}
						className="ml-2 px-3 py-1 text-sm text-blue-600 hover:text-blue-700 font-medium"
					>
						Clear filters
					</button>
				)}

				<span className="ml-auto text-sm text-gray-500">
					{totalSources} {totalSources === 1 ? 'source' : 'sources'}
				</span>
			</div>
		</div>
	);
}
